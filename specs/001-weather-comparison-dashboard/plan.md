# Implementation Plan: Two-City Weather Comparison Dashboard

**Branch**: `001-weather-comparison-dashboard` | **Date**: 2026-11-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-weather-comparison-dashboard/spec.md`

## Summary

Deliver a local, single-tenant dashboard that compares current and historical weather for two
cities. A Django/DRF backend owns all data access: it retrieves current conditions from
OpenWeather, persists every reading as an append-only `WeatherData` row, serves recent reads
through a mandatory Redis cache with documented TTLs, and pushes new observations to browsers
over Django Channels WebSockets. A React/Vite/Ant Design single-page app is built once and served
by Django at the site root; all of its UI-authored copy is Spanish while the repository artifacts
remain English. Opening `/` without a pair reads the latest stored pair from PostgreSQL, and city
search resolves through Redis, PostgreSQL and then the provider. Celery beat refreshes recently
active cities so history accumulates without an open browser and so every connected dashboard
receives live updates. The whole system starts with `docker compose up` on a clean checkout, with
container health checks, automatic migrations, persisted volumes, and degraded-but-working behavior
when the weather credential is missing.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.6 on Node.js 20 (frontend)

**Primary Dependencies**: Django 5.1, Django REST Framework 3.15, Django Channels 4, channels-redis,
Daphne, django-redis, psycopg 3, Celery 5.4, WhiteNoise, redis 5.2.1 (pinned to keep the
channels-redis BZPOPMIN timeout compatible); React 18, Vite 5, Ant Design 5, TanStack Query 5,
Recharts 2, React Router 6

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
provider requests time-boxed at 5 s with at most 2 retries; repository artifacts in English and
all UI-authored user-facing copy in Spanish (`lang="es"`)

**Scale/Scope**: One operator, up to ~10 concurrent browser sessions, 2 compared cities per view,
roughly 2 observations per minute per tracked city (≈2.1M rows/year), 3 history windows, 1 SPA
with 4 dashboard regions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status | Evidence |
|---|---|---|---|
| I. Microspec-First, English Artifacts, Spanish UX | A single-concern microspec exists, artifacts are English and user-facing copy is Spanish | PASS | `spec.md` covers one capability; plan, research, contracts and tasks are English; the SPA declares `lang="es"`, uses Ant Design's `es_ES` locale, and all UI-authored labels, states, notices and accessibility text are Spanish |
| II. Layered Data Flow, One Direction | Browser talks only to the backend; live updates pushed via WebSocket | PASS | SPA calls `/weather/`, `/dashboard-data/`, `/weather/export/`, `/cities/search/`, `/health/`; provider credential never leaves the server; search order Redis -> PostgreSQL -> OpenWeather; WS `/ws/weather/` |
| III. Cache Is a Contract | Redis mandatory, deterministic keys, documented TTL, graceful miss | PASS | TTL table in [research.md](./research.md) and [docs/architecture.md](../../docs/architecture.md) (current 60 s, dashboard 30 s, series 60 s, geocoding 24 h, unknown city 10 min); per-city current cache and version-key invalidation on insert |
| IV. Resilience and Truthful Data | Provider failure falls back to DB, logs distinguish failure classes, no invented values | PASS | Fallback path returns `source: "stale"` with `observed_at`; structured JSON logs; comparison and charts read only stored rows; a page past the end returns 200 with an empty set |
| V. Typed Contracts and Input Validation | Serializer-validated inputs, server pagination, parameterized ORM, XSS/CSRF handling | PASS | Contracts in `contracts/openapi.yaml`; `page_size` bounded; ORM-only queries; React escaping; JSON-only POST with same-origin check; CSV formula-injection hardening; export accepts `Accept: text/csv`; channel payloads are JSON primitives |
| VI. One-Command Startup | Clean checkout boots with one command, no manual steps, data survives restarts | PASS | Compose health checks, `depends_on` ordering, entrypoint runs migrations and collectstatic, named volumes for Postgres, Redis and built SPA assets, dev-safe defaults when `.env` is absent |

**Result**: No violations. Complexity tracking records the two Celery extras, the one-shot frontend
build and the version-keyed series invalidation.

**Post-design re-check (Phase 1)**: All six gates remain PASS after the data model, REST contract,
WebSocket protocol, quickstart and the post-delivery fixes were reviewed. The design adds no direct
browser-to-provider path, documents every TTL, keeps derived values out of storage, defaults `/` to
stored data, resolves city search in the documented cache/storage/provider order, hashes channel
group names, and preserves the single-command startup through health checks and a one-shot frontend
build.

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
.gitignore
README.md
scripts/
└── verify-startup.sh
docs/
├── architecture.md
├── performance.md
└── constitution-compliance.md
backend/
├── Dockerfile
├── .dockerignore
├── conftest.py
├── entrypoint.sh
├── manage.py
├── pyproject.toml
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   ├── wsgi.py
│   └── celery.py
├── tests/
│   ├── conftest.py
│   └── fixtures.py
└── weather/
    ├── apps.py
    ├── cache.py
    ├── consumers.py
    ├── context.py
    ├── errors.py
    ├── logging.py
    ├── middleware.py
    ├── models.py
    ├── pagination.py
    ├── realtime.py
    ├── routing.py
    ├── serializers.py
    ├── signals.py
    ├── tasks.py
    ├── urls.py
    ├── views.py
    ├── services/
    │   ├── cities.py
    │   ├── csv_export.py
    │   ├── dashboard.py
    │   ├── normalization.py
    │   ├── observations.py
    │   ├── openweather.py
    │   ├── series.py
    │   └── windows.py
    ├── migrations/
    └── tests/
        ├── unit/
        ├── integration/
        └── contract/
frontend/
├── Dockerfile
├── .dockerignore
├── package.json
├── package-lock.json
├── vite.config.ts
├── tsconfig.json
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── api/
    │   └── client.ts
    ├── ws/
    │   └── useWeatherSocket.ts
    ├── components/
    │   ├── CitySelector.tsx
    │   ├── ConnectionBadge.tsx
    │   ├── CurrentComparison.tsx
    │   ├── ExportButton.tsx
    │   ├── HistoryCharts.tsx
    │   └── ObservationsTable.tsx
    ├── pages/
    │   └── Dashboard.tsx
    ├── hooks/
    │   ├── useDashboardData.ts
    │   └── useObservations.ts
    ├── lib/
    │   └── time.ts
    ├── types/
    │   └── weather.ts
    └── tests/
        ├── fixtures.ts
        ├── setup.ts
        └── mocks/
```

**Structure Decision**: Web application layout with `backend/` and `frontend/` at the repository
root. The frontend is compiled once into a shared volume and served by Django at `/`, so the
browser sees a single origin for the SPA, REST API, and WebSocket endpoint. Celery worker and beat
reuse the backend image with different commands.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Two extra Compose services (`worker`, `beat`) beyond the four-service baseline (`postgres`, `redis`, `backend`, one-shot `frontend`) | History must accumulate and dashboards must update when no browser is open; periodic ingestion is the documented purpose for Celery | Client-triggered refresh only leaves charts empty until a user visits, breaks unattended history growth, and makes live fan-out depend on a request; a background thread inside Daphne would duplicate worker semantics without supervision or retries |
| The required `frontend` service is a one-shot builder writing to a shared volume instead of a long-running server | The SPA must be served from the Django root while remaining a separate, independently built artifact | A single multi-stage backend image would remove the required frontend service; running Vite as a dev server in front of Django would violate the single-origin and single-command model |
| Version-keyed series invalidation instead of key scans | Avoids `KEYS`/`SCAN` over Redis on every insert while keeping series cache correctness | TTL-only expiry allows up to 60 s of stale charts after a new point; key scanning is O(keyspace) and is disallowed by the cache contract's efficiency requirement |

## Post-Delivery Fixes Reflected in This Plan

These changes were made during implementation and are now part of the documented design. They do
not alter the layered data flow.

| Area | Change | Evidence |
|---|---|---|
| Default view | `GET /dashboard-data/` without `cities` reads the latest stored pair from PostgreSQL; the SPA reflects it in the URL. No stored rows yields an empty payload, not a provider call. | `backend/weather/views.py`, `backend/weather/services/dashboard.py`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Dashboard.test.tsx` |
| City search | Resolution order is Redis geocoding cache -> PostgreSQL observations -> OpenWeather. `City Country` input is retried as `City,Country`; stored cities remain searchable without a provider key. | `backend/weather/services/cities.py`, `backend/weather/tests/contract/test_city_search.py` |
| Channel groups | Group names are `weather.<sha256(city_key)[:32]>`, which keeps spaces and apostrophes valid for Channels. Consumer and publisher share `weather.realtime.channel_group`. | `backend/weather/realtime.py`, `backend/weather/tests/unit/test_realtime.py`, `backend/weather/tests/contract/test_websocket.py` |
| Channel payloads | Observation payloads are normalized to JSON primitives before `group_send`, because the channel layer uses msgpack and cannot pack `Decimal`. | `backend/weather/signals.py`, `backend/weather/tests/integration/test_realtime.py` |
| Redis compatibility | `redis==5.2.1` is pinned to keep the channels-redis BZPOPMIN timeout compatible. | `backend/pyproject.toml` |
| CSV negotiation | The export view bypasses DRF renderer negotiation and accepts the SPA's `Accept: text/csv`. | `backend/weather/views.py`, `backend/weather/tests/contract/test_export.py` |
| Out-of-range pages | A page beyond the last returns HTTP 200 with an empty result set; only a page below 1 or a non-integer page is a 400. | `backend/weather/pagination.py` |
| Spanish UX | The SPA declares `lang="es"`, uses Ant Design's `es_ES` locale, and all UI-authored copy is Spanish while repository artifacts stay English; API messages remain technical detail within Spanish UI copy. | `frontend/index.html`, `frontend/src/App.tsx`, `frontend/src/**/*.tsx`, `frontend/src/hooks/useDashboardData.ts` |
