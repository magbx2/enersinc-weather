import time
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from weather.models import WeatherData

pytestmark = pytest.mark.django_db


def test_export_of_ten_thousand_rows_finishes_under_ten_seconds(api_client):
    now = timezone.now()
    start = now - timedelta(hours=23)
    rows = [
        WeatherData(
            city="Santiago",
            city_key="santiago",
            country_code="CL",
            temperature=Decimal("18.40"),
            humidity=62,
            wind_speed=Decimal("3.10"),
            timestamp=start + timedelta(seconds=index * 8),
        )
        for index in range(10_000)
    ]
    WeatherData.objects.bulk_create(rows, batch_size=2_000)

    began = time.monotonic()
    response = api_client.get("/weather/export/?city=Santiago&window=24h")
    payload = b"".join(response.streaming_content)
    elapsed = time.monotonic() - began

    assert response.status_code == 200
    assert payload.count(b"\r\n") == 10_001
    assert elapsed < 10
