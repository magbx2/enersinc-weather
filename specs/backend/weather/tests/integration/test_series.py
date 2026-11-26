from datetime import UTC, datetime

import pytest

from weather.services.series import load_series

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 11, 25, 14, 0, tzinfo=UTC)


def test_24h_series_uses_15_minute_buckets(make_observation):
    make_observation(
        "Santiago", timestamp=datetime(2026, 11, 25, 12, 1, tzinfo=UTC), temperature=10
    )
    make_observation(
        "Santiago", timestamp=datetime(2026, 11, 25, 12, 14, tzinfo=UTC), temperature=20
    )
    make_observation(
        "Santiago", timestamp=datetime(2026, 11, 25, 12, 16, tzinfo=UTC), temperature=30
    )

    series = load_series("santiago", "24h", now=NOW)

    assert [point["bucket_start"] for point in series] == [
        "2026-11-25T12:00:00Z",
        "2026-11-25T12:15:00Z",
    ]
    assert series[0]["temperature"] == pytest.approx(15.0)
    assert series[0]["sample_count"] == 2
    assert series[1]["temperature"] == pytest.approx(30.0)


def test_7d_series_uses_2_hour_buckets(make_observation):
    make_observation(
        "Santiago", timestamp=datetime(2026, 11, 24, 10, 30, tzinfo=UTC), temperature=10
    )
    make_observation(
        "Santiago", timestamp=datetime(2026, 11, 24, 11, 30, tzinfo=UTC), temperature=20
    )

    series = load_series("santiago", "7d", now=NOW)

    assert len(series) == 1
    assert series[0]["bucket_start"] == "2026-11-24T10:00:00Z"
    assert series[0]["temperature"] == pytest.approx(15.0)


def test_30d_series_uses_12_hour_buckets(make_observation):
    make_observation("Santiago", timestamp=datetime(2026, 11, 20, 1, 0, tzinfo=UTC), temperature=10)
    make_observation(
        "Santiago", timestamp=datetime(2026, 11, 20, 13, 0, tzinfo=UTC), temperature=20
    )

    series = load_series("santiago", "30d", now=NOW)

    assert [point["bucket_start"] for point in series] == [
        "2026-11-20T00:00:00Z",
        "2026-11-20T12:00:00Z",
    ]


def test_empty_buckets_are_omitted_not_zero_filled(make_observation):
    make_observation(
        "Santiago", timestamp=datetime(2026, 11, 25, 12, 5, tzinfo=UTC), temperature=10
    )

    series = load_series("santiago", "24h", now=NOW)

    assert len(series) == 1
    assert series[0]["bucket_start"] == "2026-11-25T12:00:00Z"


def test_rows_outside_the_window_are_excluded(make_observation):
    make_observation("Santiago", timestamp=datetime(2026, 11, 24, 9, 0, tzinfo=UTC), temperature=10)

    assert load_series("santiago", "24h", now=NOW) == []
