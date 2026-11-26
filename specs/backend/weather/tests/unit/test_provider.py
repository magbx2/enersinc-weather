import logging

import httpx
import pytest
import respx

from weather.services.openweather import (
    CredentialInvalid,
    OpenWeatherClient,
    ProviderUnavailable,
    RateLimited,
    UnknownCity,
)

BASE = "https://provider.test"


def client(max_retries: int = 2) -> OpenWeatherClient:
    return OpenWeatherClient(
        api_key="secret-key",
        base_url=BASE,
        timeout=1,
        max_retries=max_retries,
        backoff=0,
    )


def test_credential_errors_are_not_retried(caplog):
    caplog.set_level(logging.WARNING, logger="weather.provider")
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/geo/1.0/direct").mock(return_value=httpx.Response(401))

        with pytest.raises(CredentialInvalid):
            client().search_cities("Santiago")

    assert route.call_count == 1
    assert "secret-key" not in caplog.text


def test_server_errors_are_retried_then_mapped():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/geo/1.0/direct").mock(return_value=httpx.Response(500))

        with pytest.raises(ProviderUnavailable):
            client(max_retries=2).search_cities("Santiago")

    assert route.call_count == 3


def test_rate_limits_are_retried_then_mapped():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/geo/1.0/direct").mock(return_value=httpx.Response(429))

        with pytest.raises(RateLimited):
            client(max_retries=1).search_cities("Santiago")

    assert route.call_count == 2


def test_unknown_city_maps_to_its_own_error():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/geo/1.0/direct").mock(return_value=httpx.Response(404))

        with pytest.raises(UnknownCity):
            client().search_cities("Atlantis")


def test_network_failure_maps_to_unavailable():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/geo/1.0/direct").mock(side_effect=httpx.ConnectError("boom"))

        with pytest.raises(ProviderUnavailable):
            client(max_retries=0).search_cities("Santiago")


def test_geocoding_results_are_normalized():
    payload = [
        {"name": "Valparaíso", "lat": -33.05, "lon": -71.62, "country": "CL", "state": "Valparaiso"}
    ]
    with respx.mock(base_url=BASE) as mock:
        mock.get("/geo/1.0/direct").mock(return_value=httpx.Response(200, json=payload))

        candidates = client().search_cities("Valparaiso")

    assert candidates[0].city_key == "valparaiso"
    assert candidates[0].country_code == "CL"
    assert candidates[0].provider_city_id > 0


def test_current_weather_is_parsed_with_utc_timestamp():
    payload = {
        "id": 3871336,
        "name": "Santiago",
        "dt": 1_764_072_000,
        "main": {"temp": 18.4, "humidity": 62},
        "wind": {"speed": 3.1},
        "sys": {"country": "CL"},
    }
    with respx.mock(base_url=BASE) as mock:
        mock.get("/data/2.5/weather").mock(return_value=httpx.Response(200, json=payload))

        observation = client().current_weather(-33.45, -70.66)

    assert observation.timestamp.tzinfo is not None
    assert observation.temperature == pytest.approx(18.4)
    assert observation.country_code == "CL"


def test_unconfigured_client_never_calls_the_network():
    unconfigured = OpenWeatherClient(api_key="", base_url=BASE)
    with pytest.raises(CredentialInvalid):
        unconfigured.search_cities("Santiago")
