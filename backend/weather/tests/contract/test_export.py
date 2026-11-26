from datetime import timedelta

import pytest
from django.utils import timezone

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded(make_observation):
    now = timezone.now()
    make_observation("Santiago", timestamp=now, temperature=18.4, humidity=62, wind_speed=3.1)
    make_observation(
        "Valparaiso",
        timestamp=now - timedelta(minutes=1),
        temperature=16.2,
        humidity=71,
        wind_speed=5.4,
    )
    return now


def content_of(response) -> str:
    if getattr(response, "streaming", False):
        return b"".join(response.streaming_content).decode()
    return response.content.decode()


def test_export_has_an_attachment_header_and_column_order(api_client, seeded):
    response = api_client.get("/weather/export/?window=24h")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert "attachment" in response["Content-Disposition"]
    assert "weather-observations.csv" in response["Content-Disposition"]

    lines = content_of(response).strip().split("\r\n")
    assert lines[0] == "id,city,country_code,temperature_c,humidity_pct,wind_speed_ms,timestamp"
    assert len(lines) == 3
    assert "18.40,62,3.10" in lines[1]


def test_export_accepts_a_csv_accept_header(api_client, seeded):
    response = api_client.get("/weather/export/?window=24h", HTTP_ACCEPT="text/csv")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    lines = content_of(response).strip().split("\r\n")
    assert lines[0].startswith("id,city")


def test_export_applies_the_city_filter(api_client, seeded):
    response = api_client.get("/weather/export/?city=Santiago&window=24h")

    lines = content_of(response).strip().split("\r\n")
    assert len(lines) == 2
    assert lines[1].split(",")[1] == "Santiago"


def test_export_ignores_pagination(api_client, seeded):
    response = api_client.get("/weather/export/?page=2&page_size=1&window=24h")

    lines = content_of(response).strip().split("\r\n")
    assert len(lines) == 3


def test_export_with_no_matches_is_header_only(api_client, seeded):
    response = api_client.get("/weather/export/?city=Nowhere&window=24h")

    lines = content_of(response).strip().split("\r\n")
    assert len(lines) == 1
    assert lines[0].startswith("id,city")


def test_export_rejects_invalid_ranges(api_client, seeded):
    response = api_client.get(
        "/weather/export/?start=2026-11-25T12:00:00Z&end=2026-11-25T11:00:00Z"
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_range"
