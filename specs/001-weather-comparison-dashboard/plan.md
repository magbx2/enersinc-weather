# Implementation Plan: Two-City Weather Comparison Dashboard

**Branch**: `001-weather-comparison-dashboard` | **Date**: 2026-11-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-weather-comparison-dashboard/spec.md`

## Summary

Deliver a local, single-tenant dashboard that compares current and historical weather for two
cities. A Django/DRF backend owns all data access: it retrieves current conditions from
OpenWeather, persists every reading as an append-only `WeatherData` row, serves recent reads
through a mandatory Redis cache with documented TTLs, and pushes new observations to browsers
over Django Channels WebSockets. A React/Vite/Ant Design single-page app is built once and served
by Django at the site root. Celery beat refreshes recently active cities so history accumulates
without an open browser and so every connected dashboard receives live updates. The whole system
starts with `docker compose up` on a clean checkout, with container health checks, automatic
migrations, persisted volumes, and degraded-but-working behavior when the weather credential is
missing.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.6 on Node.js 20 (frontend)

**Primary Dependencies**: Django 5.1, Django REST Framework 3.15, Django Channels 4, channels-redis,
Daphne, django-redis, psycopg 3, Celery 5.4, WhiteNoise; React 18, Vite 5, Ant Design 5,
TanStack Query 5, Recharts 2, React Router 6

**Storage**: PostgreSQL 16 for the append-only observation history; Redis 7 for the response cache,
the Channels group layer, and the Celery broker

**Testing**: pytest + pytest-django + respx + freezegun + Channels `WebsocketCommunicator` for the
backend; Vitest + React Testing Library + MSW for the frontend

**Target Platform**: Linux containers (Docker Compose); current versions of major desktop and
mobile browsers

**Project Type**: Web application (backend + frontend in one repository, one served origin)

**Performance Goals**: Cached dashboard payload p95 under 500 ms; cold dashboard payload p95 under
2 s; new-observation fan-out under 5 s end to end; 10,000-row CSV export under 10 s; table page
changes under 1 s

**Constraints**: One-command startup from a clean checkout; no authentication; current-condition
cache TTL fixed at 60 s; all timestamps stored and transported in UTC (ISO 8601); no fabricated,
interpolated, or estimated values; API and WebSocket reachable on the same origin as the SPA;
provider requests time-boxed at 5 s with at most 2 retries

**Scale/Scope**: One operator, up to ~10 concurrent browser sessions, 2 compared cities per view,
roughly 2 observations per minute per tracked city (≈1M rows/year), 3 history windows, 1 SPA with
4 dashboard regions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status | Evidence |
|---|---|---|---|
| I. Microspec-First, English-Only | A single-concern microspec exists and all artifacts are English | PASS | `spec.md` covers one capability; plan, research, contracts and tasks are English-only |
| II. Layered Data Flow, One Direction | Browser talks only to the backend; live updates pushed via WebSocket | PASS | SPA calls `/weather/`, `/dashboard-data/`, `/weather/export/`, `/cities/search/`, `/health/`; provider credential never leaves the server; WS `/ws/weather/` |
| III. Cache Is a Contract | Redis mandatory, deterministic keys, documented TTL, graceful miss | PASS | TTL table in [research.md](./research.md) (current 60 s, dashboard 30 s, series 60 s, geocoding 24 h, unknown city 10 min); version-key invalidation on insert |
| IV. Resilience and Truthful Data | Provider failure falls back to DB, logs distinguish failure classes, no invented values | PASS | Fallback path returns `source: "stale"` with `observed_at`; structured JSON logs; comparison and charts read only stored rows |
| V. Typed Contracts and Input Validation | Serializer-validated inputs, server pagination, parameterized ORM, XSS/CSRF handling | PASS | Contracts in `contracts/openapi.yaml`; `page_size` bounded; ORM-only queries; React escaping; JSON-only POST with same-origin check; CSV formula-injection hardening |
| VI. One-Command Startup | Clean checkout boots with one command, no manual steps, data survives restarts | PASS | Compose health checks, `depends_on` ordering, entrypoint runs migrations and collectstatic, named volumes for Postgres, Redis and built SPA assets, dev-safe defaults when `.env` is absent |

**Result**: No violations. Complexity tracking is used only to record the deliberate inclusion of
Celery worker and beat services.

**Post-design re-check (Phase 1)**: All six gates remain PASS after the data model, REST contract,
WebSocket protocol and quickstart were produced. The design adds no direct browser-to-provider path,
documents every TTL, keeps derived values out of storage, and preserves the single-command startup
through health checks and a one-shot frontend build.

## Project Structure

### Documentation (this feature)

```text
specs/001-weather-comparison-dashboard/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── openapi.yaml     # REST contract
│   └── websocket.md     # Live-update protocol
└── tasks.md             # Phase 2 output (/speckit.tasks - not created here)
```

### Source Code (repository root)

```text
docker-compose.yml
.env.example
backend/
├── Dockerfile
├── manage.py
├── pyproject.toml
├── entrypoint.sh
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   ├── wsgi.py
│   └── celery.py
├── weather/
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── pagination.py
│   ├── cache.py
│   ├── consumers.py
│   ├── routing.py
│   ├── signals.py
│   ├── tasks.py
│   ├── logging.py
│   ├── services/
│   │   ├── openweather.py
│   │   └── dashboard.py
│   ├── migrations/
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── contract/
frontend/
├── Dockerfile
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── api/
    ├── ws/
    ├── components/
    │   ├── CitySelector.tsx
    │   ├── CurrentComparison.tsx
    │   ├── HistoryCharts.tsx
    │   ├── ObservationsTable.tsx
    │   ├── ExportButton.tsx
    │   └── ConnectionBadge.tsx
    ├── pages/
    │   └── Dashboard.tsx
    ├── hooks/
    ├── types/
    └── tests/
```

**Structure Decision**: Web application layout with `backend/` and `frontend/` at the repository
root. The frontend is compiled once into a shared volume and served by Django at `/`, so the
browser sees a single origin for the SPA, REST API, and WebSocket endpoint. Celery worker and beat
reuse the backend image with different commands.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Two extra Compose services (`worker`, `beat`) beyond the four required | History must accumulate and dashboards must update when no browser is open; periodic ingestion is the documented purpose for Celery | Client-triggered refresh only leaves charts empty until a user visits, breaks unattended history growth, and makes live fan-out depend on a request; a background thread inside Daphne would duplicate worker semantics without supervision or retries |
| One-shot `frontend` build service writing to a shared volume | The SPA must be served from the Django root while remaining a separate, independently built artifact | A single multi-stage backend image would remove the required `frontend` service; running Vite as a dev server in front of Django would violate the single-origin and single-command model |
| Version-keyed series invalidation instead of key scans | Avoids `KEYS`/`SCAN` over Redis on every insert while keeping series cache correctness | TTL-only expiry allows up to 60 s of stale charts after a new point; key scanning is O(keyspace) and is disallowed by the cache contract's efficiency requirement |
