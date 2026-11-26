"""Pure city-name parsing, validation and normalization (no I/O)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from weather.errors import ApiError

MAX_CITY_LENGTH = 80
_ALLOWED_PUNCTUATION = {" ", "'", ".", "-"}
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True, slots=True)
class NormalizedCity:
    name: str
    key: str


def city_key(name: str) -> str:
    """Fold diacritics and case, collapse whitespace: ``Valparaíso`` → ``valparaiso``."""
    decomposed = unicodedata.normalize("NFKD", name)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(without_marks.casefold().split())


def normalize_city(raw: str) -> NormalizedCity:
    """Trim, validate and fold a user-supplied city name.

    Raises ``ApiError`` with ``code=invalid_city`` for anything that is not a
    plain human place name, so markup and control characters never reach the
    provider, storage or a cache key.
    """
    if not isinstance(raw, str):
        raise ApiError("invalid_city", "City name must be a string.")
    if _CONTROL.search(raw):
        raise ApiError("invalid_city", "City name contains control characters.")
    name = " ".join(raw.split())
    if not name:
        raise ApiError("invalid_city", "City name must not be empty.")
    if len(name) > MAX_CITY_LENGTH:
        raise ApiError("invalid_city", f"City name must be at most {MAX_CITY_LENGTH} characters.")
    if _CONTROL.search(name):
        raise ApiError("invalid_city", "City name contains control characters.")
    if not name[0].isalpha():
        raise ApiError("invalid_city", "City name must start with a letter.")
    for char in name:
        if char.isalpha() or char in _ALLOWED_PUNCTUATION:
            continue
        raise ApiError("invalid_city", "City name contains unsupported characters.")
    return NormalizedCity(name=name, key=city_key(name))


def normalize_pair(raw_cities: list[str]) -> list[NormalizedCity]:
    """Validate exactly two distinct cities after normalization."""
    if len(raw_cities) != 2:
        raise ApiError("invalid_city", "Exactly two cities are required.")
    first, second = (normalize_city(raw) for raw in raw_cities)
    if first.key == second.key:
        raise ApiError("duplicate_city", "The two cities must be different.")
    return [first, second]


def parse_cities_query(raw: str | None) -> list[NormalizedCity]:
    if not raw:
        raise ApiError("invalid_city", "The 'cities' query parameter is required.")
    return normalize_pair(raw.split(","))
