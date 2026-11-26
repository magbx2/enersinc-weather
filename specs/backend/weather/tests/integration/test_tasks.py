from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from weather.services.openweather import ProviderUnavailable
from weather.tasks import refresh_tracked_cities

pytestmark = pytest.mark.django_db


@pytest.fixture
def tracked_cities(make_observation):
    now = timezone.now()
    for index in range(12):
        make_observation(f"City {chr(ord('A') + index)}", timestamp=now - timedelta(minutes=index))
    for index in range(3):
        make_observation(f"Old {index}", timestamp=now - timedelta(days=3, minutes=index))


def test_refreshes_at_most_ten_recent_cities(tracked_cities):
    with patch("weather.tasks.refresh_single_city") as refresh:
        refreshed = refresh_tracked_cities.run()

    assert refreshed == 10
    assert refresh.call_count == 10
    names = [call.args[0] for call in refresh.call_args_list]
    assert all(not name.startswith("Old") for name in names)


def test_skips_inactive_cities(make_observation):
    make_observation("Recent", timestamp=timezone.now())
    make_observation("Inactive", timestamp=timezone.now() - timedelta(days=2))

    with patch("weather.tasks.refresh_single_city") as refresh:
        refresh_tracked_cities.run()

    assert [call.args[0] for call in refresh.call_args_list] == ["Recent"]


def test_provider_errors_do_not_abort_the_batch(tracked_cities):
    with patch("weather.tasks.refresh_single_city") as refresh:
        refresh.side_effect = [ProviderUnavailable("down"), None] * 6

        refreshed = refresh_tracked_cities.run()

    assert refresh.call_count == 10
    assert refreshed == 5
