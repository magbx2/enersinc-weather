"""Server pagination and shared query-parameter validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response

from weather.errors import ApiError
from weather.services.normalization import normalize_city
from weather.services.windows import DEFAULT_WINDOW, WINDOW_SPECS


@dataclass(frozen=True, slots=True)
class FilterState:
    city_key: str | None
    start: datetime | None
    end: datetime | None
    window: str


def _parse_bound(raw: str | None, label: str) -> datetime | None:
    if raw is None or raw == "":
        return None
    parsed = parse_datetime(raw)
    if parsed is None:
        raise ApiError("invalid_range", f"'{label}' must be an ISO 8601 date-time.")
    if parsed.tzinfo is None:
        raise ApiError("invalid_range", f"'{label}' must include a UTC offset.")
    return parsed.astimezone(UTC)


def parse_filters(request: Request) -> FilterState:
    params = request.query_params

    city_key: str | None = None
    raw_city = params.get("city")
    if raw_city is not None:
        city_key = normalize_city(raw_city).key

    window = params.get("window") or DEFAULT_WINDOW
    if window not in WINDOW_SPECS:
        raise ApiError("invalid_window", "Window must be one of 24h, 7d or 30d.")

    start = _parse_bound(params.get("start"), "start")
    end = _parse_bound(params.get("end"), "end")
    if start and end and start >= end:
        raise ApiError("invalid_range", "'start' must be earlier than 'end'.")

    return FilterState(city_key=city_key, start=start, end=end, window=window)


def resolve_range(
    filters: FilterState, *, now: datetime | None = None
) -> tuple[datetime, datetime]:
    """Return the effective [start, end) bounds, applying the window fallback."""
    now = now or datetime.now(UTC)
    if filters.start is None and filters.end is None:
        return now - WINDOW_SPECS[filters.window].duration, now
    start = filters.start or (now - WINDOW_SPECS[filters.window].duration)
    end = filters.end or now
    if start >= end:
        raise ApiError("invalid_range", "'start' must be earlier than 'end'.")
    return start, end


def window_duration(window: str) -> timedelta:
    return WINDOW_SPECS[window].duration


class _EmptyPage:
    """A page beyond the last one: valid request, empty result set."""

    def __init__(self, number: int, paginator: object) -> None:
        self.number = number
        self.paginator = paginator
        self.object_list: list[object] = []

    def has_next(self) -> bool:
        return False

    def has_previous(self) -> bool:
        return self.number > 1

    def previous_page_number(self) -> int:
        return self.number - 1

    def next_page_number(self) -> int:
        return self.number + 1


class WeatherPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_page_size(self, request: Request) -> int | None:
        raw = request.query_params.get(self.page_size_query_param)
        if raw is not None:
            try:
                size = int(raw)
            except (TypeError, ValueError) as exc:
                raise ApiError("invalid_pagination", "'page_size' must be an integer.") from exc
            if size < 1 or size > self.max_page_size:
                raise ApiError(
                    "invalid_pagination",
                    f"'page_size' must be between 1 and {self.max_page_size}.",
                )
            return size
        return self.page_size

    def paginate_queryset(self, queryset: Any, request: Request, view: Any = None) -> Any:
        raw_page = request.query_params.get(self.page_query_param, "1")
        try:
            page_number = int(raw_page)
        except (TypeError, ValueError) as exc:
            raise ApiError("invalid_pagination", "'page' must be a positive integer.") from exc
        if page_number < 1:
            raise ApiError("invalid_pagination", "'page' must be a positive integer.")

        try:
            return super().paginate_queryset(queryset, request, view)
        except NotFound:
            # A page past the end is a valid request with no rows, matching the
            # UI's "empty state, not an error" contract.
            page_size = self.get_page_size(request) or self.page_size
            paginator = self.django_paginator_class(queryset, page_size)
            self.request = request
            self.page = _EmptyPage(page_number, paginator)  # type: ignore[assignment]
            return []

    def get_paginated_response(self, data: Any) -> Response:
        page = self.page
        if page is None:  # pragma: no cover - paginate_queryset always sets it
            raise RuntimeError("paginate_queryset must run before get_paginated_response")
        total_pages = page.paginator.num_pages if page.paginator.count else 0
        page_size = self.get_page_size(self.request) if self.request else self.page_size
        return Response(
            {
                "count": page.paginator.count,
                "page": page.number,
                "page_size": page_size,
                "total_pages": total_pages,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )
