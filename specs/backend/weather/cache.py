"""Redis cache contract: documented keys, explicit TTLs, graceful degradation.

Every helper treats a cache failure as a miss and logs ``event=cache_error``.
A Redis outage must never fail a request (Constitution Principle III).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from django.core.cache import cache

logger = logging.getLogger("weather.cache")


def raw_key(key: str, key_prefix: str, version: int | None) -> str:
    """Keep the documented Redis keys byte-for-byte (no Django version prefix)."""
    return f"{key_prefix}{key}" if key_prefix else key


TTL: dict[str, int] = {
    "current": 60,
    "dashboard": 30,
    "series": 60,
    "geocoding": 86_400,
    "invalid_city": 600,
}


def current_key(city_key: str) -> str:
    return f"weather:current:v1:{city_key}"


def dashboard_key(city_a: str, city_b: str, window: str) -> str:
    first, second = sorted((city_a, city_b))
    return f"weather:dashboard:v1:{first}:{second}:{window}"


def series_key(city_key: str, window: str, version: int | str) -> str:
    return f"weather:series:v1:{city_key}:{window}:{version}"


def series_version_key(city_key: str) -> str:
    return f"weather:seriesver:v1:{city_key}"


def geocoding_key(query_hash: str) -> str:
    return f"geo:search:v1:{query_hash}"


def invalid_city_key(query_hash: str) -> str:
    return f"geo:invalid:v1:{query_hash}"


def _log_cache_error(operation: str, key: str, exc: Exception) -> None:
    logger.warning(
        "cache operation failed; treating as miss",
        extra={"event": "cache_error", "operation": operation, "key": key, "error": str(exc)},
    )


def get_json(key: str) -> Any | None:
    try:
        raw = cache.get(key)
    except Exception as exc:  # noqa: BLE001 - any backend failure is a miss
        _log_cache_error("get", key, exc)
        return None
    if raw is None:
        return None
    if isinstance(raw, str | bytes):
        try:
            return json.loads(raw)
        except (TypeError, ValueError) as exc:
            _log_cache_error("decode", key, exc)
            return None
    return raw


def set_json(key: str, value: Any, ttl: int) -> None:
    try:
        cache.set(key, json.dumps(value, separators=(",", ":")), timeout=ttl)
    except Exception as exc:  # noqa: BLE001
        _log_cache_error("set", key, exc)


def delete(*keys: str) -> None:
    if not keys:
        return
    try:
        cache.delete_many(list(keys))
    except Exception as exc:  # noqa: BLE001
        _log_cache_error("delete", keys[0], exc)


def get_series_version(city_key: str) -> int:
    value = get_json(series_version_key(city_key))
    return int(value) if isinstance(value, int | float | str) else 0


def bump_series_version(city_key: str) -> None:
    key = series_version_key(city_key)
    try:
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=None)
    except Exception as exc:  # noqa: BLE001
        _log_cache_error("incr", key, exc)


def invalidate_city(city_key: str) -> None:
    """Drop the current reading, rotate the series version and clear geocoding."""
    delete(current_key(city_key))
    bump_series_version(city_key)


def invalidate_dashboard(city_a: str, city_b: str, windows: tuple[str, ...]) -> None:
    delete(*(dashboard_key(city_a, city_b, window) for window in windows))
