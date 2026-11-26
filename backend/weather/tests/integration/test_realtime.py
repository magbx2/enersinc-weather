import json
from unittest.mock import patch

import pytest
from django.db import transaction
from django.utils import timezone

from weather.models import WeatherData
from weather.realtime import channel_group
from weather.services.observations import persist_observation

pytestmark = pytest.mark.django_db(transaction=True)


def sample(**overrides):
    payload = {
        "city": "Santiago",
        "country_code": "CL",
        "temperature": 18.4,
        "humidity": 62,
        "wind_speed": 3.1,
        "timestamp": timezone.now(),
    }
    payload.update(overrides)
    return payload


def test_fanout_is_emitted_only_after_commit():
    with patch("weather.signals.async_to_sync") as sender, transaction.atomic():
        persist_observation(**sample())
        # Exiting the atomic block commits and runs on_commit callbacks.
    assert sender.called


def test_rolled_back_insert_emits_nothing():
    with patch("weather.signals.async_to_sync") as sender, transaction.atomic():
        persist_observation(**sample())
        transaction.set_rollback(True)
    assert not sender.called
    assert WeatherData.objects.count() == 0


def test_fanout_targets_only_the_city_group():
    with patch("weather.signals.async_to_sync") as sender, transaction.atomic():
        persist_observation(**sample())

    group_name = sender.return_value.call_args.args[0]
    assert group_name == channel_group("santiago")
    event = sender.return_value.call_args.args[1]
    assert event["type"] == "weather.observation"
    assert event["observation"]["city_key"] == "santiago"
    assert event["observation"]["source"] == "live"
    # The channel layer needs JSON primitives: msgpack cannot pack Decimal.
    json.dumps(event)
    assert isinstance(event["observation"]["temperature"], float)
