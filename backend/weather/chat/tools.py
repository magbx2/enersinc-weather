"""Typed, backend-only tools over stored weather observations."""

from __future__ import annotations

import json
from datetime import UTC, datetime, time, timedelta
from typing import Any

from django.db import DatabaseError
from django.db.models import Avg, Max, Min, QuerySet
from django.utils.dateparse import parse_date, parse_datetime

from weather.errors import ApiError
from weather.models import WeatherData
from weather.services.normalization import NormalizedCity, normalize_city

DEFAULT_RANGE_DAYS = 30
MAX_ROWS = 100
DEFAULT_ROWS = 20

METRICS: dict[str, tuple[str, str]] = {
    "temperature": ("temperature", "celsius"),
    "humidity": ("humidity", "percent"),
    "wind_speed": ("wind_speed", "meters_per_second"),
}
STATISTICS = {"average": Avg, "minimum": Min, "maximum": Max}


class ToolArgumentError(Exception):
    """A tool could not run because its arguments were missing or invalid."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.evidence = evidence or {}
        super().__init__(message)


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "consultar_clima",
            "description": (
                "Read stored weather observations for one city in a date range. "
                "The database is the only source of truth."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": ["city"],
                "properties": {
                    "city": {"type": "string", "minLength": 1, "maxLength": 80},
                    "start": {
                        "type": "string",
                        "description": "ISO 8601 date or date-time lower bound (inclusive).",
                    },
                    "end": {
                        "type": "string",
                        "description": "ISO 8601 date or date-time upper bound (exclusive).",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_ROWS,
                        "default": DEFAULT_ROWS,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calcular_estadistica",
            "description": (
                "Compute an aggregate (average, minimum or maximum) for one metric over "
                "stored weather observations. Arithmetic is done by the database."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": ["city", "metric", "statistic"],
                "properties": {
                    "city": {"type": "string", "minLength": 1, "maxLength": 80},
                    "metric": {
                        "type": "string",
                        "enum": sorted(METRICS),
                    },
                    "statistic": {
                        "type": "string",
                        "enum": sorted(STATISTICS),
                    },
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                },
            },
        },
    },
]


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_bound(raw: Any, label: str) -> datetime | None:
    if raw is None or raw == "":
        return None
    if not isinstance(raw, str):
        raise ToolArgumentError(
            "invalid_range", f"'{label}' must be an ISO 8601 date or date-time."
        )
    # Python's fromisoformat accepts a bare date, which Django's parse_datetime
    # would return as midnight. Treat the ``YYYY-MM-DD`` form explicitly so an
    # end date still includes its whole day.
    if len(raw) == 10 and parse_date(raw) is not None:
        day = parse_date(raw)
        assert day is not None
        parsed = datetime.combine(day, time.min, tzinfo=UTC)
        if label == "end":
            parsed += timedelta(days=1)
    else:
        parsed_datetime = parse_datetime(raw)
        if parsed_datetime is None:
            raise ToolArgumentError(
                "invalid_range", f"'{label}' must be an ISO 8601 date or date-time."
            )
        parsed = parsed_datetime
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def resolve_bounds(start_raw: Any, end_raw: Any) -> tuple[datetime, datetime]:
    """Return [start, end) with the documented 30-day fallback."""
    start = _parse_bound(start_raw, "start")
    end = _parse_bound(end_raw, "end")
    now = datetime.now(UTC)
    if start is None and end is None:
        start, end = now - timedelta(days=DEFAULT_RANGE_DAYS), now
    elif start is None:
        assert end is not None
        start = end - timedelta(days=DEFAULT_RANGE_DAYS)
    elif end is None:
        end = now
    assert start is not None and end is not None
    if start >= end:
        raise ToolArgumentError("invalid_range", "'start' must be earlier than 'end'.")
    return start, end


def resolve_city(raw: Any) -> NormalizedCity:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise ToolArgumentError("missing_parameter", "The 'city' argument is required.")
    if not isinstance(raw, str):
        raise ToolArgumentError("invalid_city", "City name must be a string.")
    try:
        return normalize_city(raw)
    except ApiError as exc:
        raise ToolArgumentError(exc.code, exc.message) from exc


def _reject_unknown(arguments: dict[str, Any], allowed: set[str]) -> None:
    unknown = sorted(set(arguments) - allowed)
    if unknown:
        raise ToolArgumentError(
            "invalid_arguments",
            "Unknown tool arguments.",
            evidence={"unknown_arguments": unknown},
        )


def _evidence(
    *,
    tool: str,
    city: NormalizedCity,
    start: datetime,
    end: datetime,
    sample_count: int,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "tool": tool,
        "city": city.name,
        "city_key": city.key,
        "filters": {"start": _iso(start), "end": _iso(end)},
        "sample_count": sample_count,
        "source": "weather_data",
    }
    payload.update(extra)
    return payload


def _queryset(city: NormalizedCity, start: datetime, end: datetime) -> QuerySet[WeatherData]:
    return WeatherData.objects.filter(
        city_key=city.key, timestamp__gte=start, timestamp__lt=end
    )


def _display_city(city: NormalizedCity, queryset: QuerySet[WeatherData]) -> str:
    latest_city = queryset.order_by("-timestamp").values_list("city", flat=True).first()
    return str(latest_city) if latest_city else city.name


def consultar_clima(arguments: dict[str, Any]) -> dict[str, Any]:
    _reject_unknown(arguments, {"city", "start", "end", "limit"})
    city = resolve_city(arguments.get("city"))
    start, end = resolve_bounds(arguments.get("start"), arguments.get("end"))

    raw_limit = arguments.get("limit", DEFAULT_ROWS)
    if isinstance(raw_limit, bool) or not isinstance(raw_limit, int):
        raise ToolArgumentError(
            "invalid_limit",
            "'limit' must be an integer.",
            evidence=_evidence(
                tool="consultar_clima", city=city, start=start, end=end, sample_count=0
            ),
        )
    if raw_limit < 1 or raw_limit > MAX_ROWS:
        raise ToolArgumentError(
            "invalid_limit",
            f"'limit' must be between 1 and {MAX_ROWS}.",
            evidence=_evidence(
                tool="consultar_clima", city=city, start=start, end=end, sample_count=0
            ),
        )

    queryset = _queryset(city, start, end)
    total = queryset.count()
    rows = [
        {
            "id": row.id,
            "temperature": float(row.temperature),
            "humidity": row.humidity,
            "wind_speed": float(row.wind_speed),
            "timestamp": _iso(row.timestamp),
        }
        for row in queryset.order_by("-timestamp", "-id")[:raw_limit]
    ]
    evidence = _evidence(
        tool="consultar_clima",
        city=city,
        start=start,
        end=end,
        sample_count=total,
        matched_city=_display_city(city, queryset),
        returned=len(rows),
        limit=raw_limit,
    )
    return {
        "ok": True,
        "evidence": evidence,
        "total_matched": total,
        "returned": len(rows),
        "no_data": total == 0,
        "rows": rows,
    }


def calcular_estadistica(arguments: dict[str, Any]) -> dict[str, Any]:
    _reject_unknown(arguments, {"city", "metric", "statistic", "start", "end"})
    city = resolve_city(arguments.get("city"))
    start, end = resolve_bounds(arguments.get("start"), arguments.get("end"))
    evidence = _evidence(
        tool="calcular_estadistica", city=city, start=start, end=end, sample_count=0
    )
    metric = arguments.get("metric")
    statistic = arguments.get("statistic")
    if metric not in METRICS:
        raise ToolArgumentError(
            "invalid_metric",
            f"'metric' must be one of {', '.join(sorted(METRICS))}.",
            evidence=evidence,
        )
    if statistic not in STATISTICS:
        raise ToolArgumentError(
            "invalid_statistic",
            f"'statistic' must be one of {', '.join(sorted(STATISTICS))}.",
            evidence=evidence,
        )

    field, unit = METRICS[metric]
    queryset = _queryset(city, start, end)
    sample_count = queryset.count()
    aggregate = queryset.aggregate(value=STATISTICS[statistic](field))
    raw_value = aggregate["value"]
    value = None if raw_value is None else round(float(raw_value), 2)
    evidence = _evidence(
        tool="calcular_estadistica",
        city=city,
        start=start,
        end=end,
        sample_count=sample_count,
        matched_city=_display_city(city, queryset),
        metric=metric,
        statistic=statistic,
        unit=unit,
    )
    return {
        "ok": True,
        "evidence": evidence,
        "value": value,
        "sample_count": sample_count,
        "no_data": sample_count == 0,
    }


_DISPATCH = {
    "consultar_clima": consultar_clima,
    "calcular_estadistica": calcular_estadistica,
}


def execute_tool(name: str, arguments: Any) -> dict[str, Any]:
    """Validate and run one tool. Errors are returned, never raised to the model loop."""
    if name not in _DISPATCH:
        return {
            "ok": False,
            "error": {"code": "unknown_tool", "message": f"Unknown tool: {name}"},
            "evidence": {},
        }
    if not isinstance(arguments, dict):
        return {
            "ok": False,
            "error": {
                "code": "invalid_arguments",
                "message": "Tool arguments must be a JSON object.",
            },
            "evidence": {},
        }
    try:
        return _DISPATCH[name](arguments)
    except ToolArgumentError as exc:
        return {
            "ok": False,
            "error": {"code": exc.code, "message": exc.message},
            "evidence": exc.evidence,
        }
    except DatabaseError:
        return {
            "ok": False,
            "error": {
                "code": "database_error",
                "message": "Stored weather data is unavailable.",
            },
            "evidence": {},
        }


def execute_tool_call(name: str, raw_arguments: str | dict[str, Any] | None) -> dict[str, Any]:
    """Parse the model's JSON arguments and delegate to ``execute_tool``."""
    if isinstance(raw_arguments, dict):
        parsed: Any = raw_arguments
    elif isinstance(raw_arguments, str) and raw_arguments.strip():
        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return {
                "ok": False,
                "error": {
                    "code": "invalid_arguments",
                    "message": "Tool arguments are not valid JSON.",
                },
                "evidence": {},
            }
    else:
        parsed = {}
    return execute_tool(name, parsed)
