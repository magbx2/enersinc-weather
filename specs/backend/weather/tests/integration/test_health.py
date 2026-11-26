import pytest
from django.db import OperationalError

pytestmark = pytest.mark.django_db


def test_health_is_ok_when_every_component_is_available(api_client):
    response = api_client.get("/health/")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert body["cache"] == "up"
    assert body["provider_configured"] is True
    assert body["scheduler"] == "up"
    assert body["version"] == "1.0.0"


def test_health_is_degraded_without_a_provider_key(api_client, settings):
    settings.OPENWEATHER_API_KEY = ""

    response = api_client.get("/health/")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["provider_configured"] is False


def test_health_reports_down_when_the_database_fails(api_client, monkeypatch):
    class BrokenCursor:
        def __enter__(self):
            raise OperationalError("no database")

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr("weather.views.connection.cursor", lambda: BrokenCursor())

    response = api_client.get("/health/")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "internal_error"
    assert response.json()["error"]["details"]["database"] == "down"
