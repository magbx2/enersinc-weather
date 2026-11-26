from weather import cache


def test_keys_follow_the_documented_scheme():
    assert cache.current_key("santiago") == "weather:current:v1:santiago"
    assert (
        cache.dashboard_key("valparaiso", "santiago", "24h")
        == "weather:dashboard:v1:santiago:valparaiso:24h"
    )
    assert cache.series_key("santiago", "7d", 3) == "weather:series:v1:santiago:7d:3"
    assert cache.series_version_key("santiago") == "weather:seriesver:v1:santiago"
    assert cache.geocoding_key("abc") == "geo:search:v1:abc"
    assert cache.invalid_city_key("abc") == "geo:invalid:v1:abc"


def test_ttls_are_the_documented_values():
    assert cache.TTL == {
        "current": 60,
        "dashboard": 30,
        "series": 60,
        "geocoding": 86_400,
        "invalid_city": 600,
    }


def test_json_round_trip_and_version_bump():
    cache.set_json("probe", {"a": 1}, 30)
    assert cache.get_json("probe") == {"a": 1}

    assert cache.get_series_version("santiago") == 0
    cache.bump_series_version("santiago")
    assert cache.get_series_version("santiago") == 1


def test_cache_failures_are_treated_as_misses(monkeypatch, caplog):
    caplog.set_level("WARNING", logger="weather.cache")

    def broken(*_args, **_kwargs):
        raise ConnectionError("redis down")

    monkeypatch.setattr("weather.cache.cache.get", broken)
    monkeypatch.setattr("weather.cache.cache.set", broken)

    assert cache.get_json("probe") is None
    cache.set_json("probe", {"a": 1}, 30)
    assert "cache_error" in caplog.text or "cache operation failed" in caplog.text


def test_invalidate_city_drops_current_and_bumps_series_version():
    cache.set_json(cache.current_key("santiago"), {"temperature": 1}, 60)
    cache.invalidate_city("santiago")

    assert cache.get_json(cache.current_key("santiago")) is None
    assert cache.get_series_version("santiago") == 1
