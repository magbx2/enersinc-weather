import pytest

pytestmark = pytest.mark.django_db


def test_missing_cities_uses_the_shared_envelope(api_client):
    response = api_client.get("/dashboard-data/")

    assert response.status_code == 400
    body = response.json()
    assert set(body) == {"error"}
    error = body["error"]
    assert error["code"] == "invalid_city"
    assert error["request_id"] == response["X-Request-ID"]
    assert error["message"]


def test_invalid_pagination_uses_the_shared_envelope(api_client):
    response = api_client.get("/weather/?page=0")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_pagination"
    assert response.json()["error"]["request_id"] == response["X-Request-ID"]


def test_invalid_range_uses_the_shared_envelope(api_client):
    response = api_client.get("/weather/?start=2026-11-25T10:00:00Z&end=2026-11-25T09:00:00Z")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_range"


def test_error_envelope_never_leaks_the_provider_key(api_client, settings, provider_mock):
    import httpx

    settings.OPENWEATHER_API_KEY = "super-secret-key"
    provider_mock.get("/geo/1.0/direct").mock(return_value=httpx.Response(500))
    response = api_client.get("/dashboard-data/?cities=Santiago,Valparaiso")

    assert response.status_code == 503
    assert "super-secret-key" not in response.content.decode()
    assert "super-secret-key" not in str(response.json())


def test_responses_carry_security_headers(api_client):
    response = api_client.get("/weather/")

    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "same-origin"
    assert "default-src 'self'" in response["Content-Security-Policy"]
