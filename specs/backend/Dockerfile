# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install the project with its dev extras so the same image runs the test
# suite (docker compose exec backend pytest) and the servers.
COPY . .
RUN python -m venv /app/.venv \
    && pip install --upgrade pip \
    && pip install ".[dev]" \
    && chmod +x entrypoint.sh \
    && addgroup --system app \
    && adduser --system --ingroup app app \
    && mkdir -p /app/staticfiles /app/spa_dist \
    && chown -R app:app /app

USER app
EXPOSE 8000

# A default command keeps `docker compose run backend pytest` ergonomic: the
# entrypoint applies migrations, then runs whatever command is supplied.
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
ENTRYPOINT ["/app/entrypoint.sh"]
