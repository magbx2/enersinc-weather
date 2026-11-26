"""OpenWeather client: time-boxed, retried and mapped to typed exceptions.

The API key is read from settings and never logged, cached or returned.
"""

from __future__ import annotations

import logging
import time
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from django.conf import settings

from weather.services.normalization import city_key

logger = logging.getLogger("weather.provider")


class ProviderError(Exception):
    """Base class for provider failures that map to a client-visible code."""

    code = "provider_unavailable"


class CredentialInvalid(ProviderError):
    code = "credential_invalid"


class UnknownCity(ProviderError):
    code = "unknown_city"


class RateLimited(ProviderError):
    code = "rate_limited"


class ProviderUnavailable(ProviderError):
    code = "provider_unavailable"


@dataclass(frozen=True, slots=True)
class CityCandidate:
    name: str
    city_key: str
    country_code: str
    state: str | None
    provider_city_id: int
    latitude: float
    longitude: float


@dataclass(frozen=True, slots=True)
class CurrentWeather:
    city: str
    country_code: str | None
    temperature: float
    humidity: int
    wind_speed: float
    timestamp: datetime
    provider_city_id: int | None = None


def is_configured() -> bool:
    return bool(getattr(settings, "OPENWEATHER_API_KEY", "").strip())


def _stable_city_id(latitude: float, longitude: float) -> int:
    digest = zlib.crc32(f"{latitude:.4f},{longitude:.4f}".encode())
    return int(digest)


def _parse_timestamp(raw: Any) -> datetime:
    if not isinstance(raw, int | float):
        raise ProviderUnavailable("Provider returned no observation timestamp.")
    return datetime.fromtimestamp(float(raw), tz=UTC)


class OpenWeatherClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        backoff: float | None = None,
    ) -> None:
        self._api_key = (api_key if api_key is not None else settings.OPENWEATHER_API_KEY).strip()
        self._base_url = (base_url or settings.OPENWEATHER_BASE_URL).rstrip("/")
        self._timeout = timeout or settings.PROVIDER_TIMEOUT_SECONDS
        self._max_retries = (
            max_retries if max_retries is not None else settings.PROVIDER_MAX_RETRIES
        )
        self._backoff = (
            backoff
            if backoff is not None
            else float(getattr(settings, "PROVIDER_RETRY_BACKOFF", 0.2))
        )

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        if not self.configured:
            raise CredentialInvalid("The weather provider credential is not configured.")

        url = f"{self._base_url}{path}"
        last_error: ProviderError = ProviderUnavailable("Weather provider is unavailable.")
        attempts = self._max_retries + 1
        for attempt in range(attempts):
            try:
                response = httpx.get(
                    url,
                    params={**params, "appid": self._api_key},
                    timeout=httpx.Timeout(self._timeout),
                )
            except httpx.HTTPError as exc:
                last_error = ProviderUnavailable("Weather provider request failed.")
                logger.warning(
                    "provider request failed",
                    extra={
                        "event": "provider_failure",
                        "endpoint": path,
                        "attempt": attempt + 1,
                        "error": type(exc).__name__,
                    },
                )
                self._sleep(attempt, attempts)
                continue

            if response.status_code in {401, 403}:
                logger.warning(
                    "provider rejected the credential",
                    extra={
                        "event": "provider_failure",
                        "endpoint": path,
                        "status": response.status_code,
                    },
                )
                raise CredentialInvalid("The weather provider rejected the credential.")
            if response.status_code == 404:
                raise UnknownCity("The weather provider does not know this city.")
            if response.status_code == 429:
                last_error = RateLimited("The weather provider rate-limited the request.")
                logger.warning(
                    "provider rate limited",
                    extra={"event": "provider_failure", "endpoint": path, "status": 429},
                )
                self._sleep(attempt, attempts)
                continue
            if response.status_code >= 500:
                last_error = ProviderUnavailable("Weather provider is unavailable.")
                logger.warning(
                    "provider returned a server error",
                    extra={
                        "event": "provider_failure",
                        "endpoint": path,
                        "status": response.status_code,
                    },
                )
                self._sleep(attempt, attempts)
                continue
            if response.status_code >= 400:
                raise ProviderUnavailable("Weather provider rejected the request.")

            try:
                return response.json()
            except ValueError as exc:
                raise ProviderUnavailable("Weather provider returned invalid JSON.") from exc

        raise last_error

    def _sleep(self, attempt: int, attempts: int) -> None:
        if attempt + 1 < attempts and self._backoff > 0:
            time.sleep(self._backoff * (2**attempt))

    def search_cities(self, query: str, limit: int = 5) -> list[CityCandidate]:
        payload = self._get("/geo/1.0/direct", {"q": query, "limit": limit})
        if not isinstance(payload, list):
            raise ProviderUnavailable("Weather provider returned an invalid geocoding payload.")
        candidates: list[CityCandidate] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                latitude = float(item["lat"])
                longitude = float(item["lon"])
                name = str(item["name"]).strip()
                country = str(item.get("country") or "").upper()[:2]
            except (KeyError, TypeError, ValueError):
                continue
            candidates.append(
                CityCandidate(
                    name=name,
                    city_key=city_key(name),
                    country_code=country,
                    state=str(item["state"]) if item.get("state") else None,
                    provider_city_id=_stable_city_id(latitude, longitude),
                    latitude=latitude,
                    longitude=longitude,
                )
            )
        return candidates

    def current_weather(self, latitude: float, longitude: float) -> CurrentWeather:
        payload = self._get(
            "/data/2.5/weather",
            {"lat": latitude, "lon": longitude, "units": "metric"},
        )
        if not isinstance(payload, dict):
            raise ProviderUnavailable("Weather provider returned an invalid observation payload.")
        try:
            main = payload["main"]
            wind = payload["wind"]
            return CurrentWeather(
                city=str(payload.get("name") or "").strip(),
                country_code=(str(payload["sys"].get("country") or "").upper()[:2] or None),
                temperature=float(main["temp"]),
                humidity=int(main["humidity"]),
                wind_speed=float(wind["speed"]),
                timestamp=_parse_timestamp(payload.get("dt")),
                provider_city_id=int(payload["id"]) if payload.get("id") is not None else None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderUnavailable(
                "Weather provider returned an incomplete observation."
            ) from exc
