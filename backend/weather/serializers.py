from __future__ import annotations

import math
from typing import Any

from rest_framework import serializers

from weather.errors import ApiError
from weather.models import WeatherData
from weather.services.normalization import normalize_pair


def _ensure_finite(value: float | None, field: str) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value):
        raise serializers.ValidationError(f"{field} must be a finite number.")
    return value


class ObservationSerializer(serializers.ModelSerializer):
    timestamp = serializers.DateTimeField(format="%Y-%m-%dT%H:%M:%SZ")

    class Meta:
        model = WeatherData
        fields = (
            "id",
            "city",
            "city_key",
            "country_code",
            "temperature",
            "humidity",
            "wind_speed",
            "timestamp",
        )

    def validate_temperature(self, value: Any) -> Any:
        return _ensure_finite(float(value), "temperature")

    def validate_wind_speed(self, value: Any) -> Any:
        return _ensure_finite(float(value), "wind_speed")


class RefreshRequestSerializer(serializers.Serializer):
    cities = serializers.ListField(
        child=serializers.CharField(max_length=80, allow_blank=False, trim_whitespace=True),
        min_length=2,
        max_length=2,
    )

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ApiError("invalid_city", "Request body must be a JSON object.")
        unknown = set(data) - set(self.fields)
        if unknown:
            raise ApiError(
                "invalid_city",
                "Request body contains unknown fields.",
                details={"unknown_fields": sorted(unknown)},
            )
        return super().to_internal_value(data)

    def validate_cities(self, value: list[str]) -> list[str]:
        # Raises ApiError for duplicate or malformed names.
        normalized = normalize_pair(value)
        return [city.name for city in normalized]


class ChatRequestSerializer(serializers.Serializer):
    session_id = serializers.UUIDField(required=False)
    message = serializers.CharField(
        max_length=2000, allow_blank=False, trim_whitespace=True
    )

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ApiError("invalid_chat", "Request body must be a JSON object.")
        unknown = set(data) - set(self.fields)
        if unknown:
            raise ApiError(
                "invalid_chat",
                "Request body contains unknown fields.",
                details={"unknown_fields": sorted(unknown)},
            )
        return super().to_internal_value(data)


def _iso_timestamp(value: Any) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def chat_message_payload(message: Any) -> dict[str, Any]:
    """Serialize a persisted message and its sanitized tool runs."""
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "status": message.status,
        "error_code": message.error_code,
        "created_at": _iso_timestamp(message.created_at),
        "tool_runs": [
            {
                "name": run.name,
                "arguments": run.arguments,
                "output": run.output,
                "status": run.status,
                "error_code": run.error_code,
            }
            for run in message.tool_runs.all()
        ],
    }


class CityCandidateSerializer(serializers.Serializer):
    name = serializers.CharField()
    city_key = serializers.CharField()
    country_code = serializers.CharField(min_length=2, max_length=2)
    state = serializers.CharField(allow_null=True, required=False)
    provider_city_id = serializers.IntegerField()


class IsoDateTimeField(serializers.DateTimeField):
    """Accept the ISO strings used by cache payloads as well as datetime objects."""

    def to_representation(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        return super().to_representation(value)


class CurrentReadingSerializer(serializers.Serializer):
    temperature = serializers.FloatField()
    humidity = serializers.IntegerField(min_value=0, max_value=100)
    wind_speed = serializers.FloatField()


class SeriesPointSerializer(serializers.Serializer):
    bucket_start = IsoDateTimeField()
    temperature = serializers.FloatField()
    humidity = serializers.FloatField()
    wind_speed = serializers.FloatField()
    sample_count = serializers.IntegerField(min_value=1)


class CitySnapshotSerializer(serializers.Serializer):
    city = serializers.CharField()
    city_key = serializers.CharField()
    country_code = serializers.CharField(allow_null=True, required=False)
    source = serializers.ChoiceField(choices=["live", "stale"])  # type: ignore[assignment]
    freshness = serializers.ChoiceField(choices=["current", "stale", "unavailable"])
    observed_at = IsoDateTimeField(allow_null=True)
    age_seconds = serializers.IntegerField(allow_null=True, min_value=0)
    current = CurrentReadingSerializer(allow_null=True)
    series = SeriesPointSerializer(many=True)
    reason = serializers.CharField(required=False)


class ComparisonSerializer(serializers.Serializer):
    temperature_delta = serializers.FloatField(allow_null=True)
    humidity_delta = serializers.FloatField(allow_null=True)
    wind_speed_delta = serializers.FloatField(allow_null=True)
    warmer_city = serializers.CharField(allow_null=True)


class DashboardDataSerializer(serializers.Serializer):
    generated_at = IsoDateTimeField()
    window = serializers.ChoiceField(choices=["24h", "7d", "30d"])
    bucket = serializers.ChoiceField(choices=["15m", "2h", "12h"])
    cities = CitySnapshotSerializer(many=True)
    comparison = ComparisonSerializer()
