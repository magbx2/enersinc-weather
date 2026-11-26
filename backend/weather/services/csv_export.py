"""RFC 4180 CSV encoding with spreadsheet formula neutralization."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from typing import Any

CSV_HEADER = (
    "id",
    "city",
    "country_code",
    "temperature_c",
    "humidity_pct",
    "wind_speed_ms",
    "timestamp",
)
FORMULA_PREFIXES = ("=", "+", "-", "@")


def neutralize_cell(value: str) -> str:
    """Prefix formula-looking text with a single quote so spreadsheets treat it as text."""
    if value.startswith(FORMULA_PREFIXES):
        return f"'{value}"
    return value


def render_row(values: Iterable[Any]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow([neutralize_cell(str(value)) if value is not None else "" for value in values])
    return buffer.getvalue()


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _decimal(value: Any) -> str:
    return f"{float(value):.2f}"


def rows_from_queryset(queryset: Any) -> Iterator[str]:
    """Stream one CSV line per row without materializing the history in memory."""
    yield render_row(CSV_HEADER)
    for row in queryset.values_list(
        "id", "city", "country_code", "temperature", "humidity", "wind_speed", "timestamp"
    ).iterator(chunk_size=2000):
        identifier, city, country, temperature, humidity, wind_speed, timestamp = row
        yield render_row(
            (
                identifier,
                city,
                country or "",
                _decimal(temperature),
                int(humidity),
                _decimal(wind_speed),
                _iso(timestamp),
            )
        )
