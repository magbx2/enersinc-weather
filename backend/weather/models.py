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


class ChatSession(models.Model):
    """A chat transcript identified by a client-generated UUID.

    The id is not an authentication token: it only scopes a non-sensitive
    conversation about stored weather history.
    """

    id = models.UUIDField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"chat session {self.id}"


class ChatMessage(models.Model):
    """One user question or assistant answer, persisted for reload and audit."""

    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_CHOICES = [(ROLE_USER, "user"), (ROLE_ASSISTANT, "assistant")]

    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [(STATUS_COMPLETED, "completed"), (STATUS_FAILED, "failed")]

    session = models.ForeignKey(ChatSession, related_name="messages", on_delete=models.CASCADE)
    role = models.CharField(max_length=9, choices=ROLE_CHOICES)
    content = models.TextField(blank=True, default="")
    status = models.CharField(max_length=11, choices=STATUS_CHOICES, default=STATUS_COMPLETED)
    error_code = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["session", "created_at"], name="ix_chat_msg_session_ts")]

    def __str__(self) -> str:
        return f"{self.role} message {self.pk}"


class ToolRun(models.Model):
    """A tool invocation attached to an assistant message, with sanitized data."""

    STATUS_OK = "ok"
    STATUS_ERROR = "error"
    STATUS_CHOICES = [(STATUS_OK, "ok"), (STATUS_ERROR, "error")]

    message = models.ForeignKey(ChatMessage, related_name="tool_runs", on_delete=models.CASCADE)
    name = models.CharField(max_length=40)
    arguments = models.JSONField(default=dict)
    output = models.JSONField(default=dict)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES)
    error_code = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.name} ({self.status})"
