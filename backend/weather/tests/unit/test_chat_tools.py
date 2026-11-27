"""Unit tests for the typed chat tools and their validation boundaries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from weather.chat.tools import (
    calcular_estadistica,
    consultar_clima,
    execute_tool,
    execute_tool_call,
)

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)


@pytest.fixture
def sanitago_rows(make_observation):
    for index, temperature in enumerate([10.0, 20.0, 30.0]):
        make_observation(
            "Santiago",
            timestamp=NOW - timedelta(days=index),
            temperature=temperature,
            humidity=50 + index,
            wind_speed=2.0 + index,
        )


def test_rows_are_filtered_by_city_range_and_limit(sanitago_rows, make_observation):
    make_observation("Santiago", timestamp=NOW - timedelta(days=40), temperature=5.0)
    make_observation("Valparaiso", timestamp=NOW - timedelta(days=1), temperature=11.0)

    result = consultar_clima(
        {
            "city": "SANTIAGO",
            "start": (NOW - timedelta(days=10)).isoformat(),
            "end": (NOW + timedelta(minutes=1)).isoformat(),
            "limit": 2,
        }
    )

    assert result["ok"] is True
    assert result["total_matched"] == 3
    assert result["returned"] == 2
    assert result["no_data"] is False
    assert result["evidence"]["city_key"] == "santiago"
    assert result["evidence"]["sample_count"] == 3
    assert all(row["temperature"] in {10.0, 20.0} for row in result["rows"])


def test_stats_are_computed_from_rows_not_the_model(sanitago_rows):
    average = calcular_estadistica(
        {
            "city": "Santiago",
            "metric": "temperature",
            "statistic": "average",
            "start": (NOW - timedelta(days=10)).isoformat(),
            "end": (NOW + timedelta(minutes=1)).isoformat(),
        }
    )
    maximum = calcular_estadistica(
        {
            "city": "Santiago",
            "metric": "temperature",
            "statistic": "maximum",
            "start": (NOW - timedelta(days=10)).isoformat(),
            "end": (NOW + timedelta(minutes=1)).isoformat(),
        }
    )
    minimum_humidity = calcular_estadistica(
        {
            "city": "Santiago",
            "metric": "humidity",
            "statistic": "minimum",
            "start": (NOW - timedelta(days=10)).isoformat(),
            "end": (NOW + timedelta(minutes=1)).isoformat(),
        }
    )

    assert average["value"] == 20.0
    assert average["sample_count"] == 3
    assert maximum["value"] == 30.0
    assert minimum_humidity["value"] == 50.0
    assert average["evidence"]["metric"] == "temperature"
    assert average["evidence"]["unit"] == "celsius"


def test_missing_city_is_an_error_not_a_default():
    result = execute_tool("consultar_clima", {})
    assert result["ok"] is False
    assert result["error"]["code"] == "missing_parameter"

    result = execute_tool("calcular_estadistica", {"metric": "temperature", "statistic": "average"})
    assert result["ok"] is False
    assert result["error"]["code"] == "missing_parameter"


def test_unknown_city_is_honest_no_data():
    result = consultar_clima({"city": "Atlantis"})
    assert result["ok"] is True
    assert result["no_data"] is True
    assert result["total_matched"] == 0
    assert result["evidence"]["city_key"] == "atlantis"


def test_invalid_arguments_are_rejected():
    assert execute_tool("consultar_clima", {"city": "Santiago", "limit": 101})["error"][
        "code"
    ] == "invalid_limit"
    assert execute_tool("consultar_clima", {"city": "<script>"})["error"]["code"] == "invalid_city"
    assert execute_tool(
        "calcular_estadistica",
        {"city": "Santiago", "metric": "pressure", "statistic": "average"},
    )["error"]["code"] == "invalid_metric"
    assert execute_tool(
        "calcular_estadistica",
        {"city": "Santiago", "metric": "temperature", "statistic": "median"},
    )["error"]["code"] == "invalid_statistic"
    assert execute_tool(
        "consultar_clima", {"city": "Santiago", "unexpected": True}
    )["error"]["code"] == "invalid_arguments"


def test_invalid_range_and_bad_json_are_reported():
    bad_range = execute_tool(
        "consultar_clima",
        {"city": "Santiago", "start": "2026-11-26T00:00:00Z", "end": "2026-11-25T00:00:00Z"},
    )
    assert bad_range["error"]["code"] == "invalid_range"

    bad_json = execute_tool_call("consultar_clima", "{not json")
    assert bad_json["error"]["code"] == "invalid_arguments"


def test_date_only_end_includes_the_whole_day(sanitago_rows, make_observation):
    make_observation(
        "Santiago",
        timestamp=datetime(2026, 11, 20, 23, 0, tzinfo=UTC),
        temperature=12.5,
    )

    result = consultar_clima(
        {"city": "Santiago", "start": "2026-11-20", "end": "2026-11-20", "limit": 10}
    )

    assert result["ok"] is True
    assert result["total_matched"] == 1
    assert result["rows"][0]["temperature"] == 12.5


def test_unknown_tool_is_refused():
    result = execute_tool("drop_tables", {"city": "Santiago"})
    assert result["ok"] is False
    assert result["error"]["code"] == "unknown_tool"
