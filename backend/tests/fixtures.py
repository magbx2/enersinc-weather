"""Shared fixtures: database factory, provider mocks, frozen clock and fakes.

Imported by ``backend/conftest.py`` and the per-directory conftest files so the
same contract holds for every test package.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
import respx
from django.core.cache import cache
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from weather.models import WeatherData
from weather.services.normalization import city_key

FROZEN_NOW = datetime(2026, 11, 25, 14, 0, tzinfo=UTC)


def geocoding_payload(
    name: str, *, lat: float = -33.45, lon: float = -70.66
) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "local_names": {},
            "lat": lat,
            "lon": lon,
            "country": "CL",
            "state": "Region Metropolitana",
        }
    ]


def current_weather_payload(
    name: str,
    *,
    temperature: float = 18.4,
    humidity: int = 62,
    wind_speed: float = 3.1,
    dt: int | None = None,
) -> dict[str, Any]:
    return {
        "id": 3871336,
        "name": name,
        "dt": dt if dt is not None else int(timezone.now().timestamp()),
        "main": {"temp": temperature, "humidity": humidity},
        "wind": {"speed": wind_speed},
        "sys": {"country": "CL"},
    }


@pytest.fixture(autouse=True)
def test_settings(settings):
    """Use fast local fakes for cache and Channels; never hit real services."""
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "weather-tests",
        }
    }
    settings.CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
    }
    settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, "testserver"]
    settings.OPENWEATHER_API_KEY = "test-key"
    settings.OPENWEATHER_BASE_URL = "https://provider.test"
    settings.PROVIDER_RETRY_BACKOFF = 0
    settings.LLM_MODEL = "gpt-4o-mini"
    settings.LLM_API_KEY = "test-llm-key"
    settings.LLM_API_BASE = ""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def make_observation(db):
    def _make(
        city: str = "Santiago",
        *,
        timestamp: datetime | None = None,
        country_code: str | None = "CL",
        temperature: float = 18.4,
        humidity: int = 62,
        wind_speed: float = 3.1,
        **overrides: Any,
    ) -> WeatherData:
        return WeatherData.objects.create(
            city=city,
            city_key=city_key(city),
            country_code=country_code,
            temperature=Decimal(str(temperature)),
            humidity=humidity,
            wind_speed=Decimal(str(wind_speed)),
            timestamp=timestamp or timezone.now(),
            **overrides,
        )

    return _make


@pytest.fixture
def provider_mock():
    """respx context with dynamic geocoding and current-weather responses."""
    coordinates = {
        "santiago": (-33.45, -70.66),
        "valparaiso": (-33.05, -71.62),
    }

    with respx.mock(base_url="https://provider.test", assert_all_called=False) as mock:

        def geo(request: httpx.Request) -> httpx.Response:
            name = request.url.params.get("q", "Unknown")
            lat, lon = coordinates.get(name.casefold(), (-33.45, -70.66))
            return httpx.Response(200, json=geocoding_payload(name, lat=lat, lon=lon))

        def current(request: httpx.Request) -> httpx.Response:
            latitude = float(request.url.params.get("lat", "-33.45"))
            if latitude > -33.2:
                return httpx.Response(
                    200,
                    json=current_weather_payload(
                        "Valparaiso", temperature=16.2, humidity=71, wind_speed=5.4
                    ),
                )
            return httpx.Response(200, json=current_weather_payload("Santiago"))

        mock.get("/geo/1.0/direct").mock(side_effect=geo)
        mock.get("/data/2.5/weather").mock(side_effect=current)
        yield mock


@pytest.fixture
def frozen_clock():
    with freeze_time(FROZEN_NOW) as frozen:
        yield frozen


@pytest.fixture
def recent_timestamp() -> datetime:
    return FROZEN_NOW - timedelta(seconds=30)


# --- Chat assistant fakes -------------------------------------------------------


class FakeLiteLLM:
    """A LiteLLM stand-in that records kwargs and returns scripted replies."""

    def __init__(self, replies: list[Any]) -> None:
        self.replies = list(replies)
        self.calls: list[dict[str, Any]] = []

    def completion(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if not self.replies:
            raise AssertionError("FakeLiteLLM received more calls than scripted replies")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def llm_tool_call(name: str, arguments: dict[str, Any], call_id: str = "call_1") -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(arguments)},
                        }
                    ],
                }
            }
        ]
    }


def llm_text(content: str) -> dict[str, Any]:
    return {"choices": [{"message": {"content": content, "tool_calls": []}}]}


@pytest.fixture
def fake_llm(monkeypatch):
    """Install a fake LiteLLM module and return an installer.

    ``fake_llm([reply_one, reply_two])`` exercises the real wrapper, kwargs
    construction and response parser without network access.
    """

    def _install(replies: list[Any]) -> FakeLiteLLM:
        fake = FakeLiteLLM(replies)
        monkeypatch.setattr("weather.chat.agent._load_litellm", lambda: fake)
        return fake

    return _install
