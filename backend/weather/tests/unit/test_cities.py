import pytest

from weather.services.cities import _query_variants, resolve_city, search_candidates
from weather.services.openweather import CityCandidate

pytestmark = pytest.mark.django_db

MEDELLIN = CityCandidate(
    name="Medellín",
    city_key="medellin",
    country_code="CO",
    state="Antioquia",
    provider_city_id=3674962,
    latitude=6.2518,
    longitude=-75.5636,
)


class FakeClient:
    def __init__(self, answers: set[str]) -> None:
        self.answers = answers
        self.calls: list[str] = []

    def search_cities(self, query: str, limit: int = 5) -> list[CityCandidate]:
        self.calls.append(query)
        return [MEDELLIN] if query in self.answers else []


def test_query_variants_add_a_comma_before_the_trailing_words():
    assert _query_variants("Medellin Colombia") == ["Medellin Colombia", "Medellin,Colombia"]
    assert _query_variants("New York United States") == [
        "New York United States",
        "New York United,States",
        "New York,United States",
    ]
    assert _query_variants("Santiago") == ["Santiago"]
    assert _query_variants("Santiago,Chile") == ["Santiago,Chile"]


def test_search_retries_without_a_comma_when_the_provider_finds_nothing(monkeypatch):
    fake = FakeClient({"Medellin,Colombia"})
    monkeypatch.setattr("weather.services.cities._client", lambda: fake)

    results = search_candidates("Medellin Colombia")

    assert [candidate.name for candidate in results] == ["Medellín"]
    assert fake.calls == ["Medellin Colombia", "Medellin,Colombia"]


def test_search_accepts_comma_separated_input_from_the_ui(monkeypatch):
    fake = FakeClient({"Medellin,Colombia"})
    monkeypatch.setattr("weather.services.cities._client", lambda: fake)

    results = search_candidates("Medellin, Colombia")

    assert [candidate.name for candidate in results] == ["Medellín"]
    assert fake.calls == ["Medellin Colombia", "Medellin,Colombia"]


def test_search_miss_is_cached_under_the_original_query(monkeypatch):
    fake = FakeClient(set())
    monkeypatch.setattr("weather.services.cities._client", lambda: fake)

    assert search_candidates("Nowhere Atlantis") == []
    first_calls = list(fake.calls)

    assert search_candidates("Nowhere Atlantis") == []
    assert fake.calls == first_calls


def test_redis_cache_wins_over_postgresql(monkeypatch, make_observation):
    fake = FakeClient({"Medellin,Colombia"})
    monkeypatch.setattr("weather.services.cities._client", lambda: fake)

    first = search_candidates("Medellin Colombia")
    make_observation("Medellin", country_code="CO")
    second = search_candidates("Medellin Colombia")

    assert second == first
    assert fake.calls == ["Medellin Colombia", "Medellin,Colombia"]


def test_search_uses_stored_cities_before_the_provider(monkeypatch, make_observation):
    make_observation("Medellín", country_code="CO")
    fake = FakeClient({"Medellin,Colombia"})
    monkeypatch.setattr("weather.services.cities._client", lambda: fake)

    results = search_candidates("Medellin Colombia")

    assert [candidate.name for candidate in results] == ["Medellín"]
    assert fake.calls == []


def test_resolve_city_ignores_stored_rows_and_uses_provider_coordinates(
    monkeypatch, make_observation
):
    make_observation("Medellin", country_code="CO")
    fake = FakeClient({"Medellin"})
    monkeypatch.setattr("weather.services.cities._client", lambda: fake)

    candidate = resolve_city("Medellin")

    assert candidate.provider_city_id == MEDELLIN.provider_city_id
    assert candidate.latitude == MEDELLIN.latitude
    assert fake.calls == ["Medellin"]
