from datetime import timedelta

import httpx
import pytest
from django.utils import timezone

from weather.models import WeatherData
from weather.services.cities import normalize_pair
from weather.services.dashboard import get_dashboard

pytestmark = pytest.mark.django_db


def test_provider_success_stores_and_returns_live(provider_mock):
    cities = normalize_pair(["Santiago", "Valparaiso"])

    payload = get_dashboard(cities, "24h", refresh=True)

    assert [city["source"] for city in payload["cities"]] == ["live", "live"]
    assert WeatherData.objects.count() == 2
    newest = WeatherData.objects.get(city_key="santiago")
    assert float(newest.temperature) == pytest.approx(18.4)


def test_provider_outage_returns_the_latest_stored_row_as_stale(
    provider_mock, make_observation, settings
):
    now = timezone.now()
    make_observation("Santiago", timestamp=now - timedelta(minutes=3))
    make_observation("Valparaiso", timestamp=now - timedelta(minutes=4))
    provider_mock.get("/data/2.5/weather").mock(return_value=httpx.Response(500))

    payload = get_dashboard(normalize_pair(["Santiago", "Valparaiso"]), "24h", refresh=True)

    assert [city["source"] for city in payload["cities"]] == ["stale", "stale"]
    assert [city["freshness"] for city in payload["cities"]] == ["stale", "stale"]
    assert all(city["current"] is not None for city in payload["cities"])


def test_no_provider_and_no_rows_is_an_explicit_unavailable_state(settings):
    settings.OPENWEATHER_API_KEY = ""
    from weather.errors import ApiError

    with pytest.raises(ApiError) as error:
        get_dashboard(normalize_pair(["Santiago", "Valparaiso"]), "24h", refresh=True)

    assert error.value.code == "no_data_available"
    assert error.value.status_code == 503


def test_cached_dashboard_is_served_without_extra_queries(
    provider_mock, make_observation, django_assert_num_queries
):
    now = timezone.now()
    make_observation("Santiago", timestamp=now)
    make_observation("Valparaiso", timestamp=now)
    cities = normalize_pair(["Santiago", "Valparaiso"])

    first = get_dashboard(cities, "24h")
    assert first["window"] == "24h"

    with django_assert_num_queries(0):
        second = get_dashboard(cities, "24h")
    assert second == first


def test_new_insert_invalidates_the_cached_dashboard(make_observation):
    now = timezone.now()
    make_observation("Santiago", timestamp=now - timedelta(minutes=2), temperature=10)
    make_observation("Valparaiso", timestamp=now - timedelta(minutes=2))
    cities = normalize_pair(["Santiago", "Valparaiso"])

    first = get_dashboard(cities, "24h")
    assert first["cities"][0]["current"]["temperature"] == pytest.approx(10)

    from weather.services.observations import persist_observation

    persist_observation(
        city="Santiago",
        country_code="CL",
        temperature=22,
        humidity=50,
        wind_speed=4,
        timestamp=now,
    )

    second = get_dashboard(cities, "24h")
    assert second["cities"][0]["current"]["temperature"] == pytest.approx(22)


def test_cache_outage_falls_through_to_storage(make_observation, monkeypatch):
    make_observation("Santiago", timestamp=timezone.now())
    make_observation("Valparaiso", timestamp=timezone.now())

    def broken(*_args, **_kwargs):
        raise ConnectionError("redis down")

    monkeypatch.setattr("weather.cache.cache.get", broken)
    monkeypatch.setattr("weather.cache.cache.set", broken)
    monkeypatch.setattr("weather.cache.cache.delete_many", broken)

    payload = get_dashboard(normalize_pair(["Santiago", "Valparaiso"]), "24h")

    assert len(payload["cities"]) == 2
    assert payload["cities"][0]["current"] is not None
