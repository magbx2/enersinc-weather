from __future__ import annotations

from django.apps import AppConfig


class WeatherConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "weather"

    def ready(self) -> None:
        # Importing registers the post_save fan-out receiver.
        from weather import signals  # noqa: F401
