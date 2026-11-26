from datetime import timedelta
from decimal import Decimal

import httpx
import pytest
from django.utils import timezone

from weather.models import WeatherData

pytestmark = pytest.mark.django_db


def test_two_cities_return_two_snapshots_with_deltas(api_client, make_observation):
    now = timezone.now()
    make_observation("Santiago", temperature=18.4, humidity=62, wind_speed=3.1, timestamp=now)
    make_observation("Valparaiso", temperature=16.2, humidity=71, wind_speed=5.4, timestamp=now)

    response = api_client.get("/dashboard-data/?cities=Santiago,Valparaiso&window=24h")

    assert response.status_code == 200
    body = response.json()
    assert body["window"] == "24h"
    assert body["bucket"] == "15m"
    assert [city["city"] for city in body["cities"]] == ["Santiago", "Valparaiso"]
    assert body["comparison"]["temperature_delta"] == pytest.approx(2.2)
    assert body["comparison"]["humidity_delta"] == pytest.approx(-9)
    assert body["comparison"]["wind_speed_delta"] == pytest.approx(-2.3)
    assert body["comparison"]["warmer_city"] == "Santiago"
    assert body["cities"][0]["freshness"] == "current"
    assert body["cities"][0]["current"] == {
        "temperature": 18.4,
        "humidity": 62,
        "wind_speed": 3.1,
    }
    assert body["cities"][0]["series"]


def test_duplicate_cities_are_rejected(api_client, make_observation):
    make_observation("Santiago")

    response = api_client.get("/dashboard-data/?cities=Santiago,santiago")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "duplicate_city"


def test_unknown_city_returns_400(api_client, provider_mock):
    provider_mock.get("/geo/1.0/direct").mock(return_value=httpx.Response(200, json=[]))

    response = api_client.get("/dashboard-data/?cities=Atlantis,Valparaiso")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unknown_city"


def test_missing_data_with_provider_down_returns_503(api_client, settings):
    settings.OPENWEATHER_API_KEY = ""

    response = api_client.get("/dashboard-data/?cities=Santiago,Valparaiso")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "no_data_available"


def test_one_city_with_data_is_shown_with_the_other_unavailable(api_client, settings):
    settings.OPENWEATHER_API_KEY = ""
    WeatherData.objects.create(
        city="Santiago",
        city_key="santiago",
        country_code="CL",
        temperature=Decimal("18.40"),
        humidity=62,
        wind_speed=Decimal("3.10"),
        timestamp=timezone.now(),
    )

    response = api_client.get("/dashboard-data/?cities=Santiago,Valparaiso")

    assert response.status_code == 200
    body = response.json()
    assert body["cities"][0]["current"] is not None
    assert body["cities"][1]["current"] is None
    assert body["cities"][1]["freshness"] == "unavailable"


def test_missing_cities_parameter_uses_the_latest_stored_pair(
    api_client, settings, make_observation
):
    settings.OPENWEATHER_API_KEY = ""
    now = timezone.now()
    make_observation("Santiago", timestamp=now - timedelta(minutes=5))
    make_observation("Madrid", timestamp=now - timedelta(minutes=2))
    make_observation("Bogota", timestamp=now - timedelta(minutes=1))
    make_observation("Bogota", timestamp=now)

    response = api_client.get("/dashboard-data/")

    assert response.status_code == 200
    body = response.json()
    assert [city["city"] for city in body["cities"]] == ["Bogota", "Madrid"]
    assert body["comparison"]["temperature_delta"] is not None


def test_missing_cities_parameter_without_stored_rows_returns_empty(api_client, settings):
    settings.OPENWEATHER_API_KEY = ""

    response = api_client.get("/dashboard-data/")

    assert response.status_code == 200
    body = response.json()
    assert body["cities"] == []
    assert body["comparison"]["temperature_delta"] is None


def test_old_rows_are_marked_stale(api_client, make_observation):
    old = timezone.now() - timedelta(hours=2)
    make_observation("Santiago", timestamp=old)
    make_observation("Valparaiso", timestamp=old)

    response = api_client.get("/dashboard-data/?cities=Santiago,Valparaiso")

    assert response.status_code == 200
    assert all(city["freshness"] == "stale" for city in response.json()["cities"])
