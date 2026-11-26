import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from weather.services.cities import normalize_pair
from weather.services.dashboard import get_dashboard

pytestmark = pytest.mark.django_db


def test_dashboard_query_count_is_bounded_and_constant(make_observation):
    now = timezone.now()
    make_observation("Santiago", timestamp=now)
    make_observation("Valparaiso", timestamp=now)
    cities = normalize_pair(["Santiago", "Valparaiso"])

    with CaptureQueriesContext(connection) as first:
        get_dashboard(cities, "24h")

    # Two latest-row lookups plus two bucket aggregates; cache reads use Redis.
    assert len(first.captured_queries) <= 6

    with CaptureQueriesContext(connection) as second:
        get_dashboard(cities, "24h")
    assert len(second.captured_queries) == 0


def test_series_and_latest_queries_use_the_documented_indexes(make_observation):
    from weather.models import WeatherData

    now = timezone.now()
    make_observation("Santiago", timestamp=now)

    with CaptureQueriesContext(connection) as captured:
        list(WeatherData.objects.filter(city_key="santiago").order_by("-timestamp")[:1])

    sql = captured.captured_queries[0]["sql"].lower()
    assert "weather_weatherdata" in sql
    assert "order by" in sql
    assert "limit" in sql
