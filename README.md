# Two-City Weather Comparison Dashboard

Compare current and historical weather for two cities on a single local origin. Django owns
all provider access and storage, Redis provides the documented response cache and the live
update layer, and a React SPA is served by Django at `/`. The whole stack starts with one
command and survives restarts. Repository artifacts and code are English; every visible string
authored by the dashboard is Spanish.

## Quick start

```bash
docker compose up
```

Then open <http://localhost:8000/>. No `.env`, migration, seed or build step is required.
Opening `/` shows the two cities with the most recent stored observations (and the full stored
history in the table), so there is never an empty first screen. The first run builds images and
takes a few minutes; later runs are fast.

`OPENWEATHER_API_KEY` is optional. Without it the stack still boots in **degraded mode**:
health reports `provider_configured: false`, live refreshes fall back to stored rows marked
stale, and the dashboard never fabricates values.

```bash
cp .env.example .env   # optional overrides
docker compose up
```

Verify readiness at any time:

```bash
./scripts/verify-startup.sh
curl -s http://localhost:8000/health/ | jq
```

## What is included

- Side-by-side current comparison with signed deltas, timestamps, freshness and source badges.
- Time-series charts over 24 h, 7 d and 30 d plus a server-paginated, city-filtered table.
- Live updates over Django Channels (`/ws/weather/`) with reconnection, deduplication and a
  visible connection state.
- CSV export of the filtered window with RFC 4180 quoting and formula-injection hardening.
- Mandatory Redis cache with deterministic keys, documented TTLs and O(1) invalidation.
- Celery worker/beat ingesting recently active cities every minute.
- Stored-default root view and city search that falls back from Redis to PostgreSQL to the provider.
- Spanish dashboard copy (`lang="es"`) while the repository and contracts stay English.

## Architecture at a glance

```text
Browser (React SPA)
   │  REST + WebSocket (same origin)
   ▼
Django / DRF / Channels ──► Redis (cache, group layer, broker)
   │
   ├──► PostgreSQL (append-only WeatherData)
   └──► OpenWeather (server-side only, 5 s timeout, max 2 retries)
```

Details, including the cache key/TTL table and error taxonomy, live in
[docs/architecture.md](docs/architecture.md). Measured targets are recorded in
[docs/performance.md](docs/performance.md).

## Development

Everything runs in containers, so the host needs only Docker with Compose v2.20+.

```bash
# Backend tests (no network access required)
docker compose exec backend pytest -q
docker compose exec backend ruff check .
docker compose exec backend mypy weather config

# Frontend tests and type checks
docker compose run --rm frontend npm test -- --run
docker compose run --rm frontend npm run typecheck
docker compose run --rm frontend npm run lint
```

The frontend can also run against the compose backend with `npm install && npm run dev` in
`frontend/`; Vite proxies `/weather`, `/dashboard-data`, `/cities`, `/health` and `/ws` to
port 8000.

### Layout

```text
backend/      Django project (config/) and weather app (weather/)
frontend/     Vite + React + Ant Design SPA
scripts/      verify-startup.sh
specs/        Specification, plan, research, contracts and tasks
docs/         Architecture and performance notes
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `weather` | Local database, created automatically |
| `REDIS_URL` | `redis://redis:6379/0` | Cache, Channels layer and Celery broker |
| `OPENWEATHER_API_KEY` | empty | Empty means documented degraded mode |
| `OPENWEATHER_BASE_URL` | `https://api.openweathermap.org` | Override for a compatible provider or proxy |
| `DJANGO_SECRET_KEY` | dev value | Override outside local use |
| `DJANGO_DEBUG` | `false` | Debug pages are never on by default |
| `BACKEND_PORT` | `8000` | Published host port |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,backend` | Hosts accepted by Django and Channels |

## Behavior under failure

| Situation | Result |
|---|---|
| Provider key missing or rejected | Boot succeeds; readings come from storage and are marked stale |
| Provider unavailable during city search | Stored cities still appear; the provider is only the third resolution step |
| Provider slow, 5xx or rate-limited | Retried twice, then the latest stored row is returned as stale |
| Redis down | Requests still succeed from PostgreSQL; cache errors are logged as `cache_error` |
| No rows at all and provider unavailable | `503` with `no_data_available`; the UI shows an explicit empty state |
| WebSocket dropped | Client reconnects with exponential backoff and jitter; snapshot removes gaps |

`docker compose down` preserves data in `pg_data`, `redis_data` and `spa_dist`.
`docker compose down -v` is the only destructive variant.

## Documentation

- [.specify/memory/constitution.md](.specify/memory/constitution.md) — project principles, including
  the English-artifacts/Spanish-UX rule.
- [specs/001-weather-comparison-dashboard/quickstart.md](specs/001-weather-comparison-dashboard/quickstart.md)
  — validation scenarios and recorded results.
- [specs/001-weather-comparison-dashboard/contracts/openapi.yaml](specs/001-weather-comparison-dashboard/contracts/openapi.yaml)
  — REST contract.
- [specs/001-weather-comparison-dashboard/contracts/websocket.md](specs/001-weather-comparison-dashboard/contracts/websocket.md)
  — live protocol.
- [docs/architecture.md](docs/architecture.md) — data flow, cache contract, error taxonomy.
- [docs/constitution-compliance.md](docs/constitution-compliance.md) — principle-by-principle review.
# enersinc-weather
