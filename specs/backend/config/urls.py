"""Root URL configuration.

The SPA catch-all is registered last and never shadows API, static, health or
WebSocket routes.
"""

from django.urls import include, path, re_path

from weather.views import health, spa

urlpatterns = [
    path("health/", health, name="health"),
    path("", include("weather.urls")),
    re_path(
        r"^(?!static/|ws/|health/|weather/|dashboard-data/|cities/).*$", spa, name="spa"
    ),
]
