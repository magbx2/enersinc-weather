"""Provider-backed city search and resolution with documented caching."""

from __future__ import annotations

import hashlib
import logging

from django.db.models import Max, Q

from weather import cache
from weather.errors import ApiError
from weather.models import WeatherData
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


def _query_variants(name: str) -> list[str]:
    """Return provider queries for a free-form search.

    OpenWeather geocoding expects ``City,Country`` and returns nothing for
    ``City Country``. Try the text as typed first, then split the trailing one
    or two words into a country/state field (``Medellin,Colombia``).
    """
    if "," in name:
        return [name]
    parts = name.split()
    variants = [name]
    for count in range(1, min(2, len(parts) - 1) + 1):
        head = " ".join(parts[:-count])
        tail = " ".join(parts[-count:])
        variants.append(f"{head},{tail}")
    return variants


def _search_terms(name: str) -> list[str]:
    """DB search terms: the full text, then the city part of each variant."""
    terms: list[str] = []
    seen: set[str] = set()
    for variant in _query_variants(name):
        head = variant.split(",", 1)[0].strip()
        folded = head.casefold()
        if head and folded not in seen:
            seen.add(folded)
            terms.append(head)
    return terms


def _search_provider(name: str, limit: int) -> list[CityCandidate]:
    client = _client()
    for variant in _query_variants(name):
        candidates = client.search_cities(variant, limit)
        if candidates:
            return candidates
    return []


def _stored_candidates(name: str, limit: int) -> list[CityCandidate]:
    """PostgreSQL step of the search pipeline: cities already observed."""
    found: dict[str, CityCandidate] = {}
    for term in _search_terms(name):
        key = city_key(term)
        if not key:
            continue
        rows = (
            WeatherData.objects.filter(Q(city_key__contains=key) | Q(city__icontains=term))
            .values("city_key")
            .annotate(
                last_seen=Max("timestamp"),
                city=Max("city"),
                country_code=Max("country_code"),
            )
            .order_by("-last_seen", "city_key")[:limit]
        )
        for row in rows:
            found.setdefault(
                row["city_key"],
                CityCandidate(
                    name=row["city"],
                    city_key=row["city_key"],
                    country_code=row["country_code"] or "",
                    state=None,
                    provider_city_id=0,
                    latitude=0.0,
                    longitude=0.0,
                ),
            )
        if found:
            return list(found.values())[:limit]
    return list(found.values())[:limit]


def _provider_candidates(name: str, limit: int) -> list[CityCandidate]:
    """Redis cache + OpenWeather step, used when PostgreSQL has no matches."""
    digest = _query_hash(name, limit)
    cached = cache.get_json(cache.geocoding_key(digest))
    if isinstance(cached, list):
        return [_dict_to_candidate(item) for item in cached if isinstance(item, dict)]
    if cache.get_json(cache.invalid_city_key(digest)) is not None:
        return []
    if not is_configured():
        return []

    candidates = _search_provider(name, limit)
    if not candidates:
        cache.set_json(cache.invalid_city_key(digest), True, cache.TTL["invalid_city"])
        return []
    cache.set_json(
        cache.geocoding_key(digest),
        [_candidate_to_dict(candidate) for candidate in candidates],
        cache.TTL["geocoding"],
    )
    return candidates


def search_candidates(query: str, limit: int = 5) -> list[CityCandidate]:
    """Search in documented order: Redis cache, PostgreSQL, then OpenWeather.

    An unconfigured provider returns no candidates instead of failing, which is
    the documented degraded mode.
    """
    # Accept "City, Country" search text: a comma is a separator here, not
    # part of the city name, so it never reaches validation or the cache key.
    normalized = normalize_city(query.replace(",", " "))
    safe_limit = max(1, min(int(limit), _SEARCH_LIMIT_MAX))

    # 1. Redis: positive geocoding results cached for 24 h.
    digest = _query_hash(normalized.name, safe_limit)
    cached = cache.get_json(cache.geocoding_key(digest))
    if isinstance(cached, list):
        return [_dict_to_candidate(item) for item in cached if isinstance(item, dict)]

    # 2. PostgreSQL: cities that already have stored observations.
    stored = _stored_candidates(normalized.name, safe_limit)
    if stored:
        return stored

    # 3. OpenWeather, with its negative cache to avoid hammering the provider.
    return _provider_candidates(normalized.name, safe_limit)


def resolve_city(name: str) -> CityCandidate:
    """Resolve a name to one provider candidate or raise ``unknown_city``.

    Stored rows are deliberately skipped: refreshing needs the provider's
    latitude/longitude, which ``WeatherData`` does not persist.
    """
    normalized = normalize_city(name)
    candidates = _provider_candidates(normalized.name, 5)
    if not candidates:
        raise ApiError("unknown_city", f"No weather source found for '{normalized.name}'.")
    for candidate in candidates:
        if candidate.city_key == normalized.key:
            return candidate
    return candidates[0]


def is_known_name(name: str) -> bool:
    """Cheap check used by the WebSocket consumer before opening a subscription."""
    normalized = normalize_city(name)
    if WeatherData.objects.filter(city_key=normalized.key).exists():
        return True
    return bool(search_candidates(normalized.name, limit=1))
