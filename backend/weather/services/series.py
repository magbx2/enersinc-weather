"""Bucketed time-series aggregation backed by PostgreSQL ``date_trunc``."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from django.db.models import Avg, Count
from django.db.models.expressions import RawSQL
from django.db.models.fields import DateTimeField

from weather import cache
from weather.models import WeatherData
from weather.services.windows import WINDOW_SPECS


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _round(value: Any) -> float:
    return round(float(value), 2)


def load_series(city_key: str, window: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Return cached or freshly computed buckets; empty buckets are omitted."""
    spec = WINDOW_SPECS[window]
    now = now or datetime.now(UTC)
    start = now - spec.duration
    version = cache.get_series_version(city_key)
    key = cache.series_key(city_key, window, version)
    cached = cache.get_json(key)
    if isinstance(cached, list):
        return [item for item in cached if isinstance(item, dict)]

    rows = (
        WeatherData.objects.filter(city_key=city_key, timestamp__gte=start, timestamp__lte=now)
        .annotate(bucket=RawSQL(spec.bucket_sql, [], output_field=DateTimeField()))
        .values("bucket")
        .annotate(
            temperature=Avg("temperature"),
            humidity=Avg("humidity"),
            wind_speed=Avg("wind_speed"),
            sample_count=Count("id"),
        )
        .order_by("bucket")
    )
    series = [
        {
            "bucket_start": _iso(row["bucket"]),
            "temperature": _round(row["temperature"]),
            "humidity": _round(row["humidity"]),
            "wind_speed": _round(row["wind_speed"]),
            "sample_count": int(row["sample_count"]),
        }
        for row in rows
    ]
    cache.set_json(key, series, cache.TTL["series"])
    return series
