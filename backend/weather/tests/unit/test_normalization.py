import pytest

from weather.errors import ApiError
from weather.services.normalization import (
    city_key,
    normalize_city,
    normalize_pair,
    parse_cities_query,
)


def test_diacritics_and_case_fold_into_a_stable_key():
    assert city_key("Valparaíso") == "valparaiso"
    assert city_key("  SAN   José  ") == "san jose"
    assert city_key("Zürich") == "zurich"


def test_normalization_trims_and_collapses_whitespace():
    city = normalize_city("  San   Juan  ")
    assert city.name == "San Juan"
    assert city.key == "san juan"


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "<script>alert(1)</script>", "123 City", "San\nJuan", "a" * 81, "O'Higgins"],
)
def test_invalid_city_names_are_rejected(raw):
    if raw == "O'Higgins":
        assert normalize_city(raw).key == "o'higgins"
        return
    with pytest.raises(ApiError) as error:
        normalize_city(raw)
    assert error.value.code == "invalid_city"


def test_pairs_must_be_distinct_after_normalization():
    with pytest.raises(ApiError) as error:
        normalize_pair(["Santiago", "santiago"])
    assert error.value.code == "duplicate_city"

    with pytest.raises(ApiError):
        normalize_pair(["Santiago"])
    with pytest.raises(ApiError):
        normalize_pair(["Santiago", "Lima", "Quito"])


def test_query_parameter_parsing():
    cities = parse_cities_query("Santiago,Valparaíso")
    assert [city.key for city in cities] == ["santiago", "valparaiso"]

    with pytest.raises(ApiError):
        parse_cities_query(None)
