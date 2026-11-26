"""Django settings for the two-city weather comparison dashboard.

Every value is environment-driven with a safe local default so that
`docker compose up` succeeds on a clean checkout without a `.env` file.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", ["localhost", "127.0.0.1", "testserver"])

INSTALLED_APPS = [
    "daphne",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "channels",
    "weather",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "weather.middleware.RequestIdMiddleware",
    "django.middleware.common.CommonMiddleware",
    "weather.middleware.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

# --- Database -----------------------------------------------------------------


def _database_from_url(url: str) -> dict[str, object]:
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL must use the postgres:// scheme")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": (parsed.path or "/weather").lstrip("/"),
        "USER": parsed.username or "weather",
        "PASSWORD": parsed.password or "",
        "HOST": parsed.hostname or "localhost",
        "PORT": str(parsed.port or 5432),
    }


_database_url = os.environ.get("DATABASE_URL", "").strip()
if _database_url:
    DATABASES = {"default": _database_from_url(_database_url)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "weather"),
            "USER": os.environ.get("POSTGRES_USER", "weather"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "weather"),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
DATABASES["default"]["OPTIONS"] = {"options": "-c timezone=UTC"}

# --- Cache, Channels and Celery ----------------------------------------------

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "",
        "KEY_FUNCTION": "weather.cache.raw_key",
        "TIMEOUT": 60,
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = None
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULE = {
    "refresh-tracked-cities-every-minute": {
        "task": "weather.tasks.refresh_tracked_cities",
        "schedule": 60.0,
    }
}

# --- Weather provider ----------------------------------------------------------

OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "").strip()
OPENWEATHER_BASE_URL = os.environ.get(
    "OPENWEATHER_BASE_URL", "https://api.openweathermap.org"
).rstrip("/")
PROVIDER_TIMEOUT_SECONDS = float(os.environ.get("PROVIDER_TIMEOUT_SECONDS", "5"))
PROVIDER_MAX_RETRIES = int(os.environ.get("PROVIDER_MAX_RETRIES", "2"))
PROVIDER_RETRY_BACKOFF = float(os.environ.get("PROVIDER_RETRY_BACKOFF", "0.2"))
CURRENT_FRESHNESS_SECONDS = 60

# --- Internationalization and time --------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

# --- Static files and the SPA --------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
SPA_DIST_DIR = Path(os.environ.get("SPA_DIST_DIR", BASE_DIR / "spa_dist"))
STATICFILES_DIRS = [SPA_DIST_DIR] if SPA_DIST_DIR.exists() else []
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
WHITENOISE_MAX_AGE = 31536000
WHITENOISE_IMMUTABLE_FILE_TEST = lambda _path, _url: True  # noqa: E731

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Security -------------------------------------------------------------------

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self' ws: wss:; "
    "font-src 'self' data:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)

# --- Django REST Framework ------------------------------------------------------

REST_FRAMEWORK = {
    # No authentication is in scope; avoid DRF's implicit dependency on
    # django.contrib.auth (which this project deliberately does not install).
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "weather.errors.api_exception_handler",
    "COERCE_DECIMAL_TO_STRING": False,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "refresh": os.environ.get("THROTTLE_REFRESH", "30/min"),
        "export": os.environ.get("THROTTLE_EXPORT", "20/min"),
    },
}

# --- Logging --------------------------------------------------------------------

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "weather.logging.JsonFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        # Propagate to the root console handler so request ids and JSON fields
        # are formatted exactly once per record.
        "weather": {"handlers": [], "level": LOG_LEVEL, "propagate": True},
        "django.request": {"handlers": [], "level": "WARNING", "propagate": True},
    },
}
