"""HTTP endpoints: health, dashboard, refresh, search, history and CSV export."""

from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import (
    FileResponse,
    HttpRequest,
    HttpResponse,
    JsonResponse,
    StreamingHttpResponse,
)
from django.views.decorators.http import require_GET
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from weather.errors import ApiError, envelope
from weather.models import WeatherData
from weather.pagination import WeatherPagination, parse_filters, resolve_range
from weather.serializers import (
    CityCandidateSerializer,
    ObservationSerializer,
    RefreshRequestSerializer,
)
from weather.services.cities import normalize_pair, parse_cities_query, search_candidates
from weather.services.csv_export import rows_from_queryset
from weather.services.dashboard import get_dashboard, latest_cities
from weather.services.openweather import is_configured
from weather.services.windows import WINDOW_SPECS

logger = logging.getLogger("weather.views")

SERVICE_VERSION = "1.0.0"


# --- Health -------------------------------------------------------------------


@require_GET
def health(_request: HttpRequest) -> JsonResponse:
    database = "up"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        database = "down"
        logger.exception("database health check failed", extra={"event": "database_error"})

    cache_status = "up"
    try:
        cache.set("health:probe", "1", timeout=5)
        if cache.get("health:probe") != "1":
            cache_status = "down"
    except Exception:
        cache_status = "down"
        logger.warning("cache health check failed", extra={"event": "cache_error"})

    provider_configured = is_configured()
    if database == "down":
        overall = "down"
    elif cache_status == "down" or not provider_configured:
        overall = "degraded"
    else:
        overall = "ok"

    details = {
        "database": database,
        "cache": cache_status,
        "provider_configured": provider_configured,
        "scheduler": "up" if cache_status == "up" else "unknown",
        "version": SERVICE_VERSION,
    }
    if overall == "down":
        body = envelope(
            "internal_error",
            "Storage is unavailable and the API cannot serve data.",
            details,
            getattr(_request, "request_id", None),
        )
        return JsonResponse(body, status=503)
    return JsonResponse({"status": overall, **details}, status=200)


# --- Dashboard ------------------------------------------------------------------


def _parse_refresh_flag(raw: str | None) -> bool:
    if raw is None or raw == "":
        return False
    if raw.lower() in {"1", "true", "yes", "on"}:
        return True
    if raw.lower() in {"0", "false", "no", "off"}:
        return False
    raise ApiError("invalid_window", "'refresh' must be a boolean.")


@api_view(["GET"])
def dashboard_data(request):
    raw_cities = request.query_params.get("cities")
    # Opening "/" has no pair: fall back to what PostgreSQL already stores.
    cities = parse_cities_query(raw_cities) if raw_cities else latest_cities()
    window = request.query_params.get("window") or "24h"
    if window not in WINDOW_SPECS:
        raise ApiError("invalid_window", "Window must be one of 24h, 7d or 30d.")
    refresh = _parse_refresh_flag(request.query_params.get("refresh"))
    payload = get_dashboard(cities, window, refresh=refresh)
    return Response(payload)


def _enforce_same_origin(request) -> None:
    """Reject cross-site writes without relying on cookies or CSRF tokens."""
    origin = request.headers.get("Origin")
    site = request.headers.get("Sec-Fetch-Site")
    if origin:
        expected = f"{request.scheme}://{request.get_host()}"
        if origin.rstrip("/") != expected:
            raise ApiError(
                "cross_origin_rejected",
                "Request origin is not allowed.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return
    if site in {"same-origin", "same-site", "none"}:
        return
    raise ApiError(
        "cross_origin_rejected",
        "Request origin is not allowed.",
        status_code=status.HTTP_403_FORBIDDEN,
    )


class RefreshView(APIView):
    throttle_scope = "refresh"

    def post(self, request):
        _enforce_same_origin(request)
        if request.content_type != "application/json":
            raise ApiError("invalid_city", "Content-Type must be application/json.")
        serializer = RefreshRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cities = normalize_pair(serializer.validated_data["cities"])
        payload = get_dashboard(cities, "24h", refresh=True)
        return Response(payload)


# --- City search ------------------------------------------------------------------


@api_view(["GET"])
def search_cities(request):
    query = request.query_params.get("q")
    if not query:
        raise ApiError("invalid_city", "The 'q' query parameter is required.")
    raw_limit = request.query_params.get("limit", "5")
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError) as exc:
        raise ApiError("invalid_pagination", "'limit' must be an integer.") from exc
    if limit < 1 or limit > 10:
        raise ApiError("invalid_pagination", "'limit' must be between 1 and 10.")

    candidates = search_candidates(query, limit)
    payload = [
        {
            "name": candidate.name,
            "city_key": candidate.city_key,
            "country_code": candidate.country_code,
            "state": candidate.state,
            "provider_city_id": candidate.provider_city_id,
        }
        for candidate in candidates
    ]
    return Response({"results": CityCandidateSerializer(payload, many=True).data})


# --- Stored history ------------------------------------------------------------------


@api_view(["GET"])
def list_weather(request):
    filters = parse_filters(request)
    queryset = WeatherData.objects.all().order_by("-timestamp", "-id")
    if filters.city_key:
        queryset = queryset.filter(city_key=filters.city_key)
    if filters.start:
        queryset = queryset.filter(timestamp__gte=filters.start)
    if filters.end:
        queryset = queryset.filter(timestamp__lt=filters.end)

    paginator = WeatherPagination()
    page = paginator.paginate_queryset(queryset, request)
    serializer = ObservationSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


class ExportView(APIView):
    throttle_scope = "export"

    def perform_content_negotiation(self, request, force=False):
        # The view streams its own CSV response, so DRF's renderer negotiation
        # has nothing to choose. Without this override, the documented
        # ``Accept: text/csv`` (what the SPA sends) is rejected because the
        # project only registers the JSON renderer.
        renderer = self.get_renderers()[0]
        return renderer, renderer.media_type

    def get(self, request):
        filters = parse_filters(request)
        start, end = resolve_range(filters)
        queryset = WeatherData.objects.filter(timestamp__gte=start, timestamp__lt=end).order_by(
            "-timestamp", "-id"
        )
        if filters.city_key:
            queryset = queryset.filter(city_key=filters.city_key)

        response = StreamingHttpResponse(rows_from_queryset(queryset), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="weather-observations.csv"'
        response["Cache-Control"] = "no-store"
        return response


# --- SPA ---------------------------------------------------------------------------


@require_GET
def spa(request: HttpRequest) -> HttpResponse | FileResponse:
    index: Path = settings.STATIC_ROOT / "index.html"
    if not index.exists():
        index = settings.SPA_DIST_DIR / "index.html"
    if not index.exists():
        return HttpResponse(
            "The dashboard bundle is missing. Run `docker compose up` to build it.",
            status=503,
            content_type="text/plain; charset=utf-8",
        )
    response = FileResponse(index.open("rb"), content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    return response
