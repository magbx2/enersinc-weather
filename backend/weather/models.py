from __future__ import annotations

from django.db import models


class WeatherData(models.Model):
    """One append-only weather reading for one city.

    Derived values (deltas, buckets, freshness) are never stored; they are
    rebuilt from these rows so every displayed number is traceable.
    """

    id = models.BigAutoField(primary_key=True)
    city = models.CharField(max_length=120)
    city_key = models.CharField(max_length=120)
    country_code = models.CharField(max_length=2, null=True, blank=True)
    temperature = models.DecimalField(max_digits=5, decimal_places=2)
    humidity = models.SmallIntegerField()
    wind_speed = models.DecimalField(max_digits=5, decimal_places=2)
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["city_key", "timestamp"], name="uq_weather_city_timestamp"
            ),
            models.CheckConstraint(
                condition=models.Q(humidity__gte=0, humidity__lte=100),
                name="ck_weather_humidity",
            ),
            models.CheckConstraint(
                condition=models.Q(wind_speed__gte=0), name="ck_weather_wind_nonneg"
            ),
            models.CheckConstraint(
                condition=models.Q(temperature__gte=-100, temperature__lte=70),
                name="ck_weather_temperature",
            ),
            models.CheckConstraint(
                condition=models.Q(city_key__regex=r"^.{1,120}$"),
                name="ck_weather_city_key",
            ),
        ]
        indexes = [
            models.Index(fields=["city_key", "-timestamp"], name="ix_weather_city_ts_desc"),
            models.Index(fields=["-timestamp"], name="ix_weather_ts_desc"),
            models.Index(fields=["city_key"], name="ix_weather_city"),
        ]
        ordering = ["-timestamp", "-id"]

    def __str__(self) -> str:
        return f"{self.city} @ {self.timestamp:%Y-%m-%dT%H:%M:%SZ}"
