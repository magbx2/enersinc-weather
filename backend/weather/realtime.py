"""Channel-layer naming shared by websocket consumers and observation fan-out."""

from __future__ import annotations

import hashlib


def channel_group(city_key: str) -> str:
    """Return a Channels-valid group name for any normalized city key.

    City keys keep spaces and apostrophes (``new york``, ``o'brien``), but
    Channels only accepts ASCII alphanumerics, hyphens, underscores and
    periods in group names. Hashing gives every key a stable, collision-safe
    name that both the consumer and the publisher compute identically.
    """
    digest = hashlib.sha256(city_key.encode("utf-8")).hexdigest()[:32]
    return f"weather.{digest}"
