"""Provider-backed city search and resolution with documented caching."""

from __future__ import annotations

import hashlib
import logging

from weather import cache
from weather.errors import ApiError
from weather.services.normalization import (
    MAX_CITY_LENGTH,
    NormalizedCity,
    city_key,
    normalize_city,
    normalize_pair,
    parse_cities_query,
)
from weather.services.openweather import CityCandidate, OpenWeatherClient, is_configured

logger = logging.getLogger("weather.cities")

_SEARCH_LIMIT_MAX = 10

__all__ = [
    "MAX_CITY_LENGTH",
    "NormalizedCity",
    "city_key",
    "is_known_name",
    "normalize_city",
    "normalize_pair",
    "parse_cities_query",
    "resolve_city",
    "search_candidates",
]


def _client() -> OpenWeatherClient:
    return OpenWeatherClient()


def _query_hash(query: str, limit: int) -> str:
    return hashlib.sha256(f"{city_key(query)}:{limit}".encode()).hexdigest()[:32]


def _candidate_to_dict(candidate: CityCandidate) -> dict[str, object]:
    return {
        "name": candidate.name,
        "city_key": candidate.city_key,
        "country_code": candidate.country_code,
        "state": candidate.state,
        "provider_city_id": candidate.provider_city_id,
        "latitude": candidate.latitude,
        "longitude": candidate.longitude,
    }


def _dict_to_candidate(item: dict[str, object]) -> CityCandidate:
    return CityCandidate(
        name=str(item["name"]),
        city_key=str(item["city_key"]),
        country_code=str(item["country_code"]),
        state=str(item["state"]) if item.get("state") is not None else None,
        provider_city_id=int(str(item["provider_city_id"])),
        latitude=float(str(item["latitude"])),
        longitude=float(str(item["longitude"])),
    )


def search_candidates(query: str, limit: int = 5) -> list[CityCandidate]:
    """Search provider geocoding with 24 h positive and 10 min negative caching.

    An unconfigured provider returns no candidates instead of failing, which is
    the documented degraded mode.
    """
    normalized = normalize_city(query)
    safe_limit = max(1, min(int(limit), _SEARCH_LIMIT_MAX))
    digest = _query_hash(normalized.name, safe_limit)

    cached = cache.get_json(cache.geocoding_key(digest))
    if isinstance(cached, list):
        return [_dict_to_candidate(item) for item in cached if isinstance(item, dict)]
    if cache.get_json(cache.invalid_city_key(digest)) is not None:
        return []

    if not is_configured():
        return []

    candidates = _client().search_cities(normalized.name, safe_limit)
    if not candidates:
        cache.set_json(cache.invalid_city_key(digest), True, cache.TTL["invalid_city"])
        return []
    cache.set_json(
        cache.geocoding_key(digest),
        [_candidate_to_dict(candidate) for candidate in candidates],
        cache.TTL["geocoding"],
    )
    return candidates


def resolve_city(name: str) -> CityCandidate:
    """Resolve a name to one provider candidate or raise ``unknown_city``."""
    normalized = normalize_city(name)
    candidates = search_candidates(normalized.name, limit=5)
    if not candidates:
        raise ApiError("unknown_city", f"No weather source found for '{normalized.name}'.")
    for candidate in candidates:
        if candidate.city_key == normalized.key:
            return candidate
    return candidates[0]


def is_known_name(name: str) -> bool:
    """Cheap check used by the WebSocket consumer before opening a subscription."""
    from weather.models import WeatherData

    normalized = normalize_city(name)
    if WeatherData.objects.filter(city_key=normalized.key).exists():
        return True
    return bool(search_candidates(normalized.name, limit=1))
