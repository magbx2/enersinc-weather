"""Documented history windows and their PostgreSQL bucket expressions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True, slots=True)
class WindowSpec:
    label: str
    duration: timedelta
    bucket: str
    bucket_sql: str


WINDOW_SPECS: dict[str, WindowSpec] = {
    "24h": WindowSpec(
        label="24h",
        duration=timedelta(hours=24),
        bucket="15m",
        bucket_sql=(
            "date_trunc('hour', timestamp) "
            "+ floor(extract(minute from timestamp) / 15) * interval '15 minutes'"
        ),
    ),
    "7d": WindowSpec(
        label="7d",
        duration=timedelta(days=7),
        bucket="2h",
        bucket_sql=(
            "date_trunc('day', timestamp) "
            "+ floor(extract(hour from timestamp) / 2) * interval '2 hours'"
        ),
    ),
    "30d": WindowSpec(
        label="30d",
        duration=timedelta(days=30),
        bucket="12h",
        bucket_sql=(
            "date_trunc('day', timestamp) "
            "+ floor(extract(hour from timestamp) / 12) * interval '12 hours'"
        ),
    ),
}

DEFAULT_WINDOW = "24h"
