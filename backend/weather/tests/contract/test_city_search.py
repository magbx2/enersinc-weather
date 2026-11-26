import pytest

pytestmark = pytest.mark.django_db


def test_search_uses_stored_city_when_the_provider_is_unavailable(
    api_client, settings, make_observation
):
    settings.OPENWEATHER_API_KEY = ""
    make_observation("Medellín", country_code="CO")

    response = api_client.get("/cities/search/?q=Medellin&limit=5")

    assert response.status_code == 200
    results = response.json()["results"]
    assert results[0]["name"] == "Medellín"
    assert results[0]["country_code"] == "CO"


def test_search_accepts_city_and_country_without_a_provider(api_client, settings, make_observation):
    settings.OPENWEATHER_API_KEY = ""
    make_observation("Medellín", country_code="CO")

    response = api_client.get("/cities/search/?q=Medellin, Colombia&limit=5")

    assert response.status_code == 200
    assert response.json()["results"][0]["name"] == "Medellín"
