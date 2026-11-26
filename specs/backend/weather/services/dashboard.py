"""Dashboard assembly and the refresh pipeline shared by REST, WebSocket and Celery."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.utils.dateparse import parse_datetime

from weather import cache
from weather.errors import ApiError
from weather.models import WeatherData
from weather.serializers import DashboardDataSerializer
from weather.services.cities import NormalizedCity, resolve_city
from weather.services.normalization import normalize_city
from weather.services.observations import persist_observation, validate_observation_time
from weather.services.openweather import (
    CredentialInvalid,
    OpenWeatherClient,
    ProviderUnavailable,
    RateLimited,
    UnknownCity,
)
from weather.services.series import load_series
from weather.services.windows import WINDOW_SPECS

logger = logging.getLogger("weather.dashboard")

_WINDOWS = tuple(WINDOW_SPECS)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _observation_to_cache(observation: WeatherData) -> dict[str, Any]:
    return {
        "id": observation.id,
        "city": observation.city,
        "city_key": observation.city_key,
        "country_code": observation.country_code,
        "temperature": str(observation.temperature),
        "humidity": observation.humidity,
        "wind_speed": str(observation.wind_speed),
        "timestamp": _iso(observation.timestamp),
    }


def _observation_from_cache(payload: dict[str, Any]) -> WeatherData | None:
    try:
        timestamp = parse_datetime(str(payload["timestamp"]))
        if timestamp is None:
            return None
        return WeatherData(
            id=int(payload["id"]),
            city=str(payload["city"]),
            city_key=str(payload["city_key"]),
            country_code=payload.get("country_code"),
            temperature=Decimal(str(payload["temperature"])),
            humidity=int(payload["humidity"]),
            wind_speed=Decimal(str(payload["wind_speed"])),
            timestamp=timestamp,
        )
    except (KeyError, TypeError, ValueError):
        return None


def latest_observation(city_key_value: str) -> WeatherData | None:
    cached = cache.get_json(cache.current_key(city_key_value))
    if isinstance(cached, dict):
        cached_observation = _observation_from_cache(cached)
        if cached_observation is not None:
            return cached_observation

    observation = (
        WeatherData.objects.filter(city_key=city_key_value).order_by("-timestamp", "-id").first()
    )
    if observation is not None:
        cache.set_json(
            cache.current_key(city_key_value),
            _observation_to_cache(observation),
            cache.TTL["current"],
        )
    return observation


def _current_payload(observation: WeatherData | None) -> dict[str, Any] | None:
    if observation is None:
        return None
    return {
        "temperature": float(observation.temperature),
        "humidity": observation.humidity,
        "wind_speed": float(observation.wind_speed),
    }


def _build_snapshot(
    city: NormalizedCity,
    window: str,
    *,
    source: str,
    reason: str | None,
    now: datetime,
) -> dict[str, Any]:
    observation = latest_observation(city.key)
    if observation is None:
        return {
            "city": city.name,
            "city_key": city.key,
            "country_code": None,
            "source": "stale",
            "freshness": "unavailable",
            "observed_at": None,
            "age_seconds": None,
            "current": None,
            "series": load_series(city.key, window, now=now),
            **({"reason": reason} if reason else {}),
        }

    age_seconds = max(0, int((now - observation.timestamp).total_seconds()))
    freshness = "current" if age_seconds <= settings.CURRENT_FRESHNESS_SECONDS else "stale"
    if reason:
        # A provider failure is explicit: the value is not presented as current
        # even when the stored row happens to be recent.
        freshness = "stale"
    if freshness == "current" and not reason:
        source = "live"
    snapshot: dict[str, Any] = {
        "city": observation.city,
        "city_key": observation.city_key,
        "country_code": observation.country_code,
        "source": source,
        "freshness": freshness,
        "observed_at": _iso(observation.timestamp),
        "age_seconds": age_seconds,
        "current": _current_payload(observation),
        "series": load_series(city.key, window, now=now),
    }
    if reason:
        snapshot["reason"] = reason
    return snapshot


def _comparison(cities: list[dict[str, Any]]) -> dict[str, Any]:
    first, second = cities
    if first["current"] is None or second["current"] is None:
        return {
            "temperature_delta": None,
            "humidity_delta": None,
            "wind_speed_delta": None,
            "warmer_city": None,
        }
    temperature_delta = round(first["current"]["temperature"] - second["current"]["temperature"], 2)
    humidity_delta = round(first["current"]["humidity"] - second["current"]["humidity"], 2)
    wind_speed_delta = round(first["current"]["wind_speed"] - second["current"]["wind_speed"], 2)
    warmer_city: str | None = None
    if temperature_delta > 0:
        warmer_city = first["city"]
    elif temperature_delta < 0:
        warmer_city = second["city"]
    return {
        "temperature_delta": temperature_delta,
        "humidity_delta": humidity_delta,
        "wind_speed_delta": wind_speed_delta,
        "warmer_city": warmer_city,
    }


def assemble(
    cities: list[NormalizedCity],
    window: str,
    *,
    sources: dict[str, str] | None = None,
    reasons: dict[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the dashboard payload from stored rows only; never invents values."""
    now = now or datetime.now(UTC)
    sources = sources or {}
    reasons = reasons or {}
    snapshots = [
        _build_snapshot(
            city,
            window,
            source=sources.get(city.key, "stale"),
            reason=reasons.get(city.key),
            now=now,
        )
        for city in cities
    ]
    payload = {
        "generated_at": _iso(now),
        "window": window,
        "bucket": WINDOW_SPECS[window].bucket,
        "cities": snapshots,
        "comparison": _comparison(snapshots),
    }
    # Serializers validate the outbound shape (and catch regressions in tests).
    DashboardDataSerializer(data=payload).is_valid(raise_exception=True)
    return payload


def _cache_dashboard(cities: list[NormalizedCity], window: str, payload: dict[str, Any]) -> None:
    """Cache the payload together with per-city versions.

    A version mismatch is a miss, so an insert immediately invalidates every
    dashboard payload that contains that city without scanning Redis keys.
    """
    versions = {city.key: cache.get_series_version(city.key) for city in cities}
    cache.set_json(
        cache.dashboard_key(cities[0].key, cities[1].key, window),
        {"versions": versions, "payload": payload},
        cache.TTL["dashboard"],
    )


def _read_cached_dashboard(cities: list[NormalizedCity], window: str) -> dict[str, Any] | None:
    cached = cache.get_json(cache.dashboard_key(cities[0].key, cities[1].key, window))
    if not isinstance(cached, dict) or "payload" not in cached or "versions" not in cached:
        return None
    current_versions = {city.key: cache.get_series_version(city.key) for city in cities}
    if cached["versions"] != current_versions:
        return None
    payload = cached["payload"]
    return payload if isinstance(payload, dict) else None


def _log_provider_fallback(city: NormalizedCity, exc: Exception) -> None:
    code = getattr(exc, "code", "provider_unavailable")
    logger.warning(
        "provider refresh failed; falling back to stored data",
        extra={"event": "provider_failure", "city_key": city.key, "code": code},
    )


def _refresh_city(client: OpenWeatherClient, city: NormalizedCity) -> None:
    if not client.configured:
        raise CredentialInvalid("The weather provider credential is not configured.")
    candidate = resolve_city(city.name)
    weather = client.current_weather(candidate.latitude, candidate.longitude)
    timestamp = validate_observation_time(weather.timestamp)
    persist_observation(
        city=candidate.name or weather.city or city.name,
        country_code=weather.country_code or candidate.country_code,
        temperature=weather.temperature,
        humidity=weather.humidity,
        wind_speed=weather.wind_speed,
        timestamp=timestamp,
    )


def refresh_single_city(name: str, *, now: datetime | None = None) -> WeatherData | None:
    """Scheduled ingestion path for one city; cache invalidation happens on insert."""
    city = normalize_city(name)
    client = OpenWeatherClient()
    _refresh_city(client, city)
    return latest_observation(city.key)


def refresh_cities(
    cities: list[NormalizedCity], window: str, *, now: datetime | None = None
) -> dict[str, Any]:
    """Fetch both cities, persist hits, and fall back per city on provider failure."""
    now = now or datetime.now(UTC)
    client = OpenWeatherClient()
    sources: dict[str, str] = {}
    reasons: dict[str, str] = {}

    for city in cities:
        try:
            _refresh_city(client, city)
            sources[city.key] = "live"
        except ApiError:
            # Validation errors (unknown city) are the client's to fix.
            raise
        except (CredentialInvalid, RateLimited, ProviderUnavailable, UnknownCity) as exc:
            _log_provider_fallback(city, exc)
            sources[city.key] = "stale"
            reasons[city.key] = getattr(exc, "code", "provider_unavailable")

    cache.invalidate_dashboard(cities[0].key, cities[1].key, _WINDOWS)
    payload = assemble(cities, window, sources=sources, reasons=reasons, now=now)
    if all(snapshot["current"] is None for snapshot in payload["cities"]):
        raise ApiError(
            "no_data_available",
            "No stored observations exist and the weather provider is unavailable.",
            status_code=503,
        )
    _cache_dashboard(cities, window, payload)
    return payload


def get_dashboard(
    cities: list[NormalizedCity],
    window: str,
    *,
    refresh: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Cache-aside dashboard read; implicitly fetches when storage is empty."""
    now = now or datetime.now(UTC)
    if refresh:
        return refresh_cities(cities, window, now=now)

    cached = _read_cached_dashboard(cities, window)
    if cached is not None:
        return cached

    payload = assemble(cities, window, now=now)
    if all(snapshot["current"] is None for snapshot in payload["cities"]):
        # First visit for these cities: try the provider once. This is where
        # an unknown city becomes a 400 and an outage becomes a 503.
        payload = refresh_cities(cities, window, now=now)

    _cache_dashboard(cities, window, payload)
    return payload


def snapshot_for_socket(cities: list[NormalizedCity], window: str = "24h") -> dict[str, Any]:
    """Socket snapshots read stored data only; a provider call is never required."""
    return assemble(cities, window)


__all__ = [
    "assemble",
    "get_dashboard",
    "latest_observation",
    "refresh_cities",
    "refresh_single_city",
    "snapshot_for_socket",
]
