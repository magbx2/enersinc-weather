"""Persist one provider reading and invalidate the cache contract for its city."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from weather import cache
from weather.models import WeatherData
from weather.services.normalization import city_key
from weather.services.openweather import ProviderUnavailable

logger = logging.getLogger("weather.observations")

MAX_AGE = timedelta(hours=24)
MAX_FUTURE = timedelta(minutes=10)


def validate_observation_time(timestamp: datetime, *, now: datetime | None = None) -> datetime:
    """Reject stale replays and clock-skewed readings from the provider."""
    now = now or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    if timestamp < now - MAX_AGE:
        raise ProviderUnavailable("Provider returned an observation older than 24 hours.")
    if timestamp > now + MAX_FUTURE:
        raise ProviderUnavailable("Provider returned an observation too far in the future.")
    return timestamp


def persist_observation(
    *,
    city: str,
    country_code: str | None,
    temperature: float,
    humidity: int,
    wind_speed: float,
    timestamp: datetime,
) -> tuple[WeatherData, bool]:
    """Insert an observation idempotently and refresh derived cache entries.

    The unique ``(city_key, timestamp)`` constraint makes repeated provider
    polls safe: the second write returns the existing row with ``created=False``.
    """
    key = city_key(city)
    observation, created = WeatherData.objects.get_or_create(
        city_key=key,
        timestamp=timestamp,
        defaults={
            "city": city,
            "country_code": country_code,
            "temperature": Decimal(str(temperature)),
            "humidity": int(humidity),
            "wind_speed": Decimal(str(wind_speed)),
        },
    )
    if created:
        cache.invalidate_city(key)
        logger.info(
            "stored observation",
            extra={
                "event": "observation_stored",
                "city_key": key,
                "observation_id": observation.id,
            },
        )
    return observation, created


def observation_payload(observation: WeatherData) -> dict[str, Any]:
    return {
        "id": observation.id,
        "city": observation.city,
        "city_key": observation.city_key,
        "country_code": observation.country_code,
        "temperature": float(observation.temperature),
        "humidity": observation.humidity,
        "wind_speed": float(observation.wind_speed),
        "timestamp": observation.timestamp.isoformat(),
    }
