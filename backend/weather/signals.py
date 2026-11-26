"""Fan-out: emit an observation only after its transaction commits."""

from __future__ import annotations

import json
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.utils.encoders import JSONEncoder

from weather.models import WeatherData
from weather.realtime import channel_group
from weather.serializers import ObservationSerializer

logger = logging.getLogger("weather.signals")


@receiver(post_save, sender=WeatherData, dispatch_uid="weather_observation_fanout")
def broadcast_observation(sender, instance: WeatherData, created: bool, **kwargs: object) -> None:
    if not created:
        return
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    # The channel layer serializes with msgpack (which rejects Decimal) and the
    # consumer re-encodes with json, so normalize DRF output to JSON primitives.
    payload = json.loads(json.dumps(dict(ObservationSerializer(instance).data), cls=JSONEncoder))
    payload["source"] = "live"

    def _send() -> None:
        try:
            async_to_sync(channel_layer.group_send)(
                channel_group(instance.city_key),
                {"type": "weather.observation", "observation": payload},
            )
        except Exception:
            # A Redis outage must not fail the insert that already committed.
            logger.exception("websocket fan-out failed", extra={"event": "realtime_error"})

    transaction.on_commit(_send)
