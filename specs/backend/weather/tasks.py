"""Scheduled ingestion: refresh recently active cities without aborting the batch."""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import Max
from django.utils import timezone

from weather.models import WeatherData
from weather.services.dashboard import refresh_single_city
from weather.services.openweather import ProviderError

logger = logging.getLogger("weather.tasks")

TRACKED_CITY_LIMIT = 10
ACTIVITY_WINDOW = timedelta(hours=24)


@shared_task(bind=True, max_retries=0)
def refresh_tracked_cities(self) -> int:  # noqa: ANN001
    """Refresh at most 10 cities observed in the last 24 hours.

    A provider failure for one city is logged and skipped so the rest of the
    batch still runs.
    """
    since = timezone.now() - ACTIVITY_WINDOW
    tracked = (
        WeatherData.objects.filter(timestamp__gte=since)
        .values("city_key", "city")
        .annotate(last_seen=Max("timestamp"))
        .order_by("-last_seen")[:TRACKED_CITY_LIMIT]
    )
    refreshed = 0
    for row in tracked:
        try:
            refresh_single_city(row["city"])
            refreshed += 1
        except ProviderError as exc:
            logger.warning(
                "scheduled refresh failed for city",
                extra={"event": "provider_failure", "city_key": row["city_key"], "code": exc.code},
            )
        except Exception:
            logger.exception(
                "scheduled refresh crashed for city",
                extra={"event": "task_error", "city_key": row["city_key"]},
            )
    logger.info(
        "scheduled refresh finished", extra={"event": "task_complete", "refreshed": refreshed}
    )
    return refreshed
