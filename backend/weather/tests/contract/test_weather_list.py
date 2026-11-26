from datetime import timedelta

import pytest
from django.utils import timezone

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded(make_observation):
    now = timezone.now()
    for index in range(25):
        make_observation(
            "Santiago",
            timestamp=now - timedelta(minutes=index),
            temperature=20 - index / 10,
        )
    make_observation("Valparaíso", timestamp=now - timedelta(minutes=1))
    return now


def test_default_page_size_and_total_pages(api_client, seeded):
    response = api_client.get("/weather/")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 26
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["total_pages"] == 2
    assert len(body["results"]) == 20
    assert body["next"] is not None
    assert body["previous"] is None


def test_second_page_is_non_overlapping_and_echoes_page(api_client, seeded):
    first = api_client.get("/weather/?page=1&page_size=20").json()
    second = api_client.get("/weather/?page=2&page_size=20").json()

    assert second["page"] == 2
    assert len(second["results"]) == 6
    assert {row["id"] for row in first["results"]}.isdisjoint(
        {row["id"] for row in second["results"]}
    )
    assert second["previous"] is not None


def test_page_size_bounds_are_enforced(api_client, seeded):
    assert api_client.get("/weather/?page_size=100").status_code == 200
    too_large = api_client.get("/weather/?page_size=101")
    assert too_large.status_code == 400
    assert too_large.json()["error"]["code"] == "invalid_pagination"

    non_numeric = api_client.get("/weather/?page_size=abc")
    assert non_numeric.status_code == 400
    assert non_numeric.json()["error"]["code"] == "invalid_pagination"


def test_invalid_page_returns_400(api_client, seeded):
    response = api_client.get("/weather/?page=0")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_pagination"


def test_city_filter_is_exact_and_case_insensitive(api_client, seeded):
    response = api_client.get("/weather/?city=VALPARAISO")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["city"] == "Valparaíso"
    assert body["results"][0]["city_key"] == "valparaiso"


def test_city_filter_rejects_markup(api_client, seeded):
    response = api_client.get("/weather/?city=%3Cscript%3E")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_city"


def test_start_and_end_bounds_are_applied(api_client, seeded):
    start = (seeded - timedelta(minutes=10)).isoformat()
    end = (seeded - timedelta(minutes=5)).isoformat()

    response = api_client.get("/weather/", {"start": start, "end": end})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 5
    for row in body["results"]:
        timestamp = row["timestamp"]
        assert start[:19] <= timestamp[:19] <= end[:19]


def test_invalid_ranges_are_rejected(api_client, seeded):
    reversed_range = api_client.get("/weather/?start=2026-11-25T12:00:00Z&end=2026-11-25T11:00:00Z")
    assert reversed_range.status_code == 400
    assert reversed_range.json()["error"]["code"] == "invalid_range"

    naive = api_client.get("/weather/?start=2026-11-25T12:00:00")
    assert naive.status_code == 400
    assert naive.json()["error"]["code"] == "invalid_range"

    malformed = api_client.get("/weather/?start=not-a-date")
    assert malformed.status_code == 400


def test_page_beyond_the_end_is_empty_not_an_error(api_client, seeded):
    response = api_client.get("/weather/?page=99&page_size=20")

    assert response.status_code == 200
    body = response.json()
    assert body["results"] == []
    assert body["page"] == 99
    assert body["count"] == 26
    assert body["total_pages"] == 2
