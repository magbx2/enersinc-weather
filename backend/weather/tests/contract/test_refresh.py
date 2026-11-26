from datetime import timedelta

import httpx
import pytest
from django.utils import timezone

from weather.models import WeatherData

pytestmark = pytest.mark.django_db

REFRESH_URL = "/weather/refresh/"
SAME_ORIGIN = {"HTTP_ORIGIN": "http://testserver"}


def test_json_body_and_same_origin_are_required(api_client):
    missing_origin = api_client.post(
        REFRESH_URL, {"cities": ["Santiago", "Valparaiso"]}, format="json"
    )
    assert missing_origin.status_code == 403
    assert missing_origin.json()["error"]["code"] == "cross_origin_rejected"

    wrong_origin = api_client.post(
        REFRESH_URL,
        {"cities": ["Santiago", "Valparaiso"]},
        format="json",
        HTTP_ORIGIN="http://evil.test",
    )
    assert wrong_origin.status_code == 403

    wrong_type = api_client.post(
        REFRESH_URL,
        data='{"cities":["Santiago","Valparaiso"]}',
        content_type="text/plain",
        **SAME_ORIGIN,
    )
    assert wrong_type.status_code == 400


def test_live_refresh_stores_rows_and_reports_live(api_client, provider_mock):
    response = api_client.post(
        REFRESH_URL, {"cities": ["Santiago", "Valparaiso"]}, format="json", **SAME_ORIGIN
    )

    assert response.status_code == 200
    body = response.json()
    assert [city["source"] for city in body["cities"]] == ["live", "live"]
    assert all(city["freshness"] == "current" for city in body["cities"])
    assert WeatherData.objects.count() == 2
    assert set(WeatherData.objects.values_list("city_key", flat=True)) == {
        "santiago",
        "valparaiso",
    }


def test_provider_failure_falls_back_to_the_latest_stored_row(
    api_client, provider_mock, make_observation
):
    now = timezone.now()
    make_observation("Santiago", timestamp=now - timedelta(minutes=5))
    make_observation("Valparaiso", timestamp=now - timedelta(minutes=5))
    provider_mock.get("/data/2.5/weather").mock(return_value=httpx.Response(503))

    response = api_client.post(
        REFRESH_URL, {"cities": ["Santiago", "Valparaiso"]}, format="json", **SAME_ORIGIN
    )

    assert response.status_code == 200
    body = response.json()
    assert [city["source"] for city in body["cities"]] == ["stale", "stale"]
    assert all(city["reason"] == "provider_unavailable" for city in body["cities"])
    assert all(city["current"] is not None for city in body["cities"])
    assert WeatherData.objects.count() == 2


def test_unknown_city_is_a_validation_error(api_client, provider_mock):
    provider_mock.get("/geo/1.0/direct").mock(return_value=httpx.Response(200, json=[]))

    response = api_client.post(
        REFRESH_URL, {"cities": ["Atlantis", "Valparaiso"]}, format="json", **SAME_ORIGIN
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unknown_city"


def test_duplicate_and_malformed_cities_are_rejected(api_client):
    duplicate = api_client.post(
        REFRESH_URL, {"cities": ["Santiago", "Santiago"]}, format="json", **SAME_ORIGIN
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["error"]["code"] == "duplicate_city"

    markup = api_client.post(
        REFRESH_URL, {"cities": ["<script>", "Valparaiso"]}, format="json", **SAME_ORIGIN
    )
    assert markup.status_code == 400
    assert markup.json()["error"]["code"] == "invalid_city"


def test_unknown_json_fields_are_rejected(api_client):
    response = api_client.post(
        REFRESH_URL,
        {"cities": ["Santiago", "Valparaiso"], "sql": "DROP TABLE"},
        format="json",
        **SAME_ORIGIN,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_city"


def test_refresh_is_throttled_with_a_retry_after_header(api_client, provider_mock, monkeypatch):
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(
        ScopedRateThrottle, "THROTTLE_RATES", {"refresh": "1/min", "export": "20/min"}
    )

    api_client.post(
        REFRESH_URL, {"cities": ["Santiago", "Valparaiso"]}, format="json", **SAME_ORIGIN
    )
    response = api_client.post(
        REFRESH_URL, {"cities": ["Santiago", "Valparaiso"]}, format="json", **SAME_ORIGIN
    )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert int(response["Retry-After"]) >= 1
