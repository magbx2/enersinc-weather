# Tasks: Two-City Weather Comparison Dashboard

**Input**: Design documents from `/specs/001-weather-comparison-dashboard/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included. The project constitution makes automated verification of acceptance checks a
quality gate, so each user story has contract, integration, or component tests. Write the story's
tests first and confirm they fail before implementing.

**Organization**: Tasks are grouped by user story so each story is independently implementable,
testable, and demoable. The feature is the dashboard delivery; the agent chat is a separate
microspec and is not represented here.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: `[US1]`–`[US5]`, mapping to the user stories in `spec.md`
- Every task names the exact file or directory it touches

## Path Conventions

- Backend: `backend/` (Django project in `backend/config/`, app in `backend/weather/`)
- Frontend: `frontend/` (Vite root, sources in `frontend/src/`)
- Infrastructure: repository root (`docker-compose.yml`, `.env.example`, `scripts/`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repository skeleton, dependency manifests, container definitions, and settings that
every later phase builds on.

- [X] T001 Create the repository skeleton (`backend/`, `frontend/`, `scripts/`) and `.gitignore` covering `__pycache__/`, `node_modules/`, `.env`, `dist/`, `staticfiles/`, `.pytest_cache/`
- [X] T002 Create `backend/pyproject.toml` pinning Django 5.1, DRF 3.15, Channels 4, channels-redis, daphne, django-redis, psycopg 3, Celery 5.4, WhiteNoise, plus pytest, pytest-django, respx, freezegun, ruff and mypy configuration
- [X] T003 [P] Create `frontend/package.json`, `frontend/tsconfig.json`, and `frontend/vite.config.ts` with React 18, Vite 5, TypeScript 5.6, Ant Design 5, TanStack Query 5, Recharts 2, React Router 6, Vitest, React Testing Library and MSW
- [X] T004 [P] Create `.env.example` at the repository root documenting `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `REDIS_URL`, `OPENWEATHER_API_KEY`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `BACKEND_PORT`, `ALLOWED_HOSTS`, and state that an empty provider key means degraded mode, not failure
- [X] T005 [P] Configure formatting and static analysis: ruff and mypy rules in `backend/pyproject.toml`, ESLint and Prettier in `frontend/.eslintrc.cjs` and `frontend/.prettierrc`
- [X] T006 Create `docker-compose.yml` with `postgres` (16-alpine) and `redis` (7-alpine) services, health checks, and named volumes `pg_data` and `redis_data`
- [X] T007 [P] Create `backend/Dockerfile` from `python:3.12-slim` installing the project, running as a non-root user, exposing port 8000
- [X] T008 [P] Create `frontend/Dockerfile` from `node:20-alpine` that builds the SPA into `/out` (the `spa_dist` mount) and exits 0 on success
- [X] T009 [P] Create `backend/entrypoint.sh` running `python manage.py migrate --noinput`, `python manage.py collectstatic --noinput`, then `exec daphne -b 0.0.0.0 -p 8000 config.asgi:application`
- [X] T010 [P] Create `backend/config/settings.py` reading all configuration from environment with safe defaults: `USE_TZ=True`, PostgreSQL via `DATABASE_URL` or discrete variables, `django-redis` cache, Channels Redis layer, Celery broker on Redis, WhiteNoise static serving, DRF defaults, and security headers (`nosniff`, `Referrer-Policy`, minimal CSP)
- [X] T011 [P] Create `backend/manage.py`, `backend/config/__init__.py`, `backend/config/asgi.py`, `backend/config/wsgi.py`, and the `backend/weather/` app skeleton with `apps.py` and `__init__.py`

**Checkpoint**: Manifests, containers and settings exist; no feature behavior yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared model, validation, cache contract, provider client, serializers, pagination,
error handling, routing and test harness. No user story can be completed before this phase.

**⚠️ CRITICAL**: Complete this phase before starting any user story.

- [X] T012 Create `WeatherData` in `backend/weather/models.py` with `id` (bigint PK), `city` varchar(120) not null, `city_key` varchar(120) not null, `country_code` char(2) nullable, `temperature` numeric(5,2) not null, `humidity` smallint not null, `wind_speed` numeric(5,2) not null, `timestamp` timestamptz not null, `created_at` timestamptz default now; add constraints `uq_weather_city_timestamp` on `(city_key, timestamp)`, `ck_weather_humidity` (`humidity BETWEEN 0 AND 100`), `ck_weather_wind_nonneg` (`wind_speed >= 0`), `ck_weather_temperature` (`temperature BETWEEN -100 AND 70`), and `ck_weather_city_key` (`length(city_key) BETWEEN 1 AND 120`); add indexes `ix_weather_city_ts_desc` on `(city_key, timestamp DESC)`, `ix_weather_ts_desc` on `(timestamp DESC)`, and `ix_weather_city` on `(city_key)`
- [X] T013 Generate `backend/weather/migrations/0001_initial.py` from the model and confirm the migration applies against PostgreSQL without warnings
- [X] T014 Create `backend/weather/services/cities.py`: trim input, enforce 1–80 characters and pattern `^[\p{L}][\p{L} .'-]*$`, reject control characters and markup, fold diacritics into `city_key`, collapse whitespace, and raise `invalid_city` / `duplicate_city` errors for identical normalized pairs
- [X] T015 Create `backend/weather/cache.py` with the documented TTL constants (`current=60`, `dashboard=30`, `series=60`, `geocoding=86400`, `invalid_city=600`), key builders `weather:current:v1:{city_key}`, `weather:dashboard:v1:{city_a}:{city_b}:{window}`, `weather:series:v1:{city_key}:{window}:{version}`, `weather:seriesver:v1:{city_key}`, `geo:search:v1:{hash}` and `geo:invalid:v1:{hash}`, plus safe get/set/delete/version-bump helpers that treat any Redis error as a cache miss and log `event=cache_error`
- [X] T016 Create `backend/weather/services/openweather.py` with geocoding and current-weather calls, 5-second connect/read timeouts, at most 2 retries with exponential backoff on 429/5xx/network errors, no retry on 401/403/404, and typed exceptions mapping to `credential_invalid`, `unknown_city`, `rate_limited`, `provider_unavailable`; never log or return the API key
- [X] T017 Create `backend/weather/serializers.py` with `ObservationSerializer`, `RefreshRequestSerializer` (exactly 2 items, `uniqueItems: true`, each 1–80 characters, `additionalProperties: false`), `CityCandidateSerializer`, and dashboard payload serializers; reject non-finite numeric values
- [X] T018 Create `backend/weather/pagination.py` with a page-number paginator (`page` minimum 1, `page_size` default 20 and maximum 100, ordering `-timestamp`, `page` and `page_size` echoed in the payload) plus shared filter parsing for `city`, `start`, `end` and `window` (`24h`, `7d`, `30d`), enforcing `start < end`
- [X] T019 Create `backend/weather/errors.py` and `backend/weather/logging.py` with the shared error envelope `{error: {code, message, details, request_id}}`, an exception handler registered in DRF settings, a request-id middleware, and JSON logging that distinguishes `provider_failure`, `cache_error` and `database_error`
- [X] T020 Create `backend/config/urls.py` and `backend/weather/urls.py` mounting `/health/`, `/weather/`, `/dashboard-data/`, `/weather/refresh/`, `/weather/export/` and `/cities/search/`, with the SPA catch-all reserved for the final route
- [X] T021 Create `backend/config/celery.py` and register it in `backend/config/__init__.py` with Redis broker URL from settings, `timezone="UTC"`, and an empty beat schedule placeholder
- [X] T022 Create the backend test harness: `backend/tests/conftest.py` with database fixtures, `WeatherData` factory helpers, a `respx` provider mock fixture, a frozen-clock fixture, and pytest-django configuration so tests never perform network calls
- [X] T023 Create `backend/weather/tests/contract/test_error_envelope.py` asserting every error response uses the shared envelope, includes `request_id`, and exposes no secrets
- [X] T024 Create the frontend test harness: `frontend/src/tests/setup.ts` with jest-dom and an MSW server, `frontend/src/tests/mocks/handlers.ts`, and Vitest configuration in `frontend/vite.config.ts`

**Checkpoint**: Model, cache, provider, validation, errors and tests are ready; user stories can
proceed in parallel.

---

## Phase 3: User Story 1 - Compare two cities side by side (Priority: P1) 🎯 MVP

**Goal**: A visitor selects two distinct cities and sees current temperature, humidity, wind
speed, observation times, per-metric differences, and freshness, with clear validation and
degraded-state handling.

**Independent Test**: From a running stack, select two cities and confirm both panels render
stored observations with timestamps and deltas; selecting the same city twice or a nonsense city
produces a validation message and no fabricated values.

### Tests for User Story 1 ⚠️

- [X] T025 [P] [US1] Contract test for `GET /dashboard-data/` in `backend/weather/tests/contract/test_dashboard_data.py`: two distinct cities return exactly two snapshots with deltas and freshness; duplicates return 400 `duplicate_city`; unknown names return 400; missing data with provider down returns 503 `no_data_available`
- [X] T026 [P] [US1] Contract test for `POST /weather/refresh/` in `backend/weather/tests/contract/test_refresh.py`: JSON body required, same-origin header required (403 `cross_origin_rejected`), live result stored, stale fallback returned on provider failure, and throttle responses use `Retry-After`
- [X] T027 [P] [US1] Integration test for the comparison flow in `backend/weather/tests/integration/test_compare_flow.py`: provider success stores one row and returns `source: live`; provider outage returns the latest stored row with `freshness: stale`; no provider and no rows yields an explicit unavailable state
- [X] T028 [P] [US1] Component test for city selection in `frontend/src/components/CitySelector.test.tsx`: debounced search, rejecting a duplicate city, rejecting an empty query, and rendering the unknown-city message
- [X] T029 [P] [US1] Component test for the comparison panels in `frontend/src/components/CurrentComparison.test.tsx`: three metrics per city, signed deltas, observation timestamps, and loading, empty, error and stale indicators

### Implementation for User Story 1

- [X] T030 [US1] Implement the dashboard assembly service in `backend/weather/services/dashboard.py`: fetch the latest row per city, compute per-metric deltas and `warmer_city`, derive `freshness` from `age_seconds <= 60`, and return `null` values when a city has no row instead of zeroes
- [X] T031 [US1] Implement `GET /dashboard-data/` in `backend/weather/views.py` using the 30-second dashboard cache key, `refresh=true` support, request-id logging, and the documented error envelope
- [X] T032 [US1] Implement `POST /weather/refresh/` in `backend/weather/views.py`: validate the two cities, fetch through the provider client, insert observations, invalidate the affected cache keys, and return the assembled snapshot with per-city `source`
- [X] T033 [US1] Implement `GET /cities/search/` in `backend/weather/views.py` proxying provider geocoding with `limit` 1–10, 24-hour positive caching, 10-minute negative caching, and `invalid_city` for malformed queries
- [X] T034 [US1] Add DRF throttle classes and rates for refresh and export endpoints in `backend/config/settings.py`, and verify the 429 envelope in a test
- [X] T035 [US1] Create the typed API client in `frontend/src/api/client.ts` and payload types in `frontend/src/types/weather.ts`, including abort support, error-envelope parsing, and no direct provider or absolute external URLs
- [X] T036 [US1] Implement `frontend/src/components/CitySelector.tsx` with Ant Design AutoComplete, 300 ms debounce, keyboard navigation, duplicate rejection, and accessible labels and messages
- [X] T037 [US1] Implement `frontend/src/components/CurrentComparison.tsx` with side-by-side metric panels that stack below 768 px, signed deltas, UTC-derived local timestamps, and freshness/source badges
- [X] T038 [US1] Implement `frontend/src/pages/Dashboard.tsx` and update `frontend/src/App.tsx` so the two selected cities live in the URL query string and deep links restore the view
- [X] T039 [US1] Add loading skeletons, an empty "choose two cities" state, an error state with retry, and a stale-data banner for the comparison region in `frontend/src/components/CurrentComparison.tsx`
- [X] T040 [US1] Wire TanStack Query in `frontend/src/hooks/useDashboardData.ts` with a 60-second refetch interval, manual refresh mutation, and cache keys that include both city keys and the window
- [X] T041 [US1] Create `frontend/src/lib/time.ts` for timezone-aware timestamp formatting and relative age labels, with unit tests in `frontend/src/lib/time.test.ts`
- [X] T042 [US1] Run the US1 test subsets (`backend/weather/tests/contract/test_dashboard_data.py`, `backend/weather/tests/contract/test_refresh.py`, `backend/weather/tests/integration/test_compare_flow.py`, `frontend/src/components/*.test.tsx`), fix failures, and record the commands in the story checkpoint

**Checkpoint**: MVP works — two cities can be compared against live or stored data.

---

## Phase 4: User Story 2 - Start the whole system with a single command (Priority: P1)

**Goal**: A clean checkout with no `.env` starts with `docker compose up` only: ordered startup,
automatic migrations and static assets, persisted volumes, health reporting, and degraded mode
without a provider key.

**Independent Test**: From a clean checkout with no configuration and no running containers, run
`docker compose up`, then `scripts/verify-startup.sh`; the dashboard loads and health reports
components. Stop, start again, and confirm stored rows survive.

### Tests for User Story 2 ⚠️

- [X] T043 [P] [US2] Integration test for health states in `backend/weather/tests/integration/test_health.py`: `ok` with database, cache and provider configured; `degraded` with an empty provider key; `down`/503 when the database check fails
- [X] T044 [P] [US2] Create `scripts/verify-startup.sh` that fails unless `/health/` answers, `/` returns the SPA shell, and an API route returns JSON, with no manual step in between

### Implementation for User Story 2

- [X] T045 [US2] Implement `GET /health/` in `backend/weather/views.py` checking a database round-trip, a Redis ping, provider configuration and scheduler reachability, returning `status: ok|degraded|down` and 503 only when storage is unusable
- [X] T046 [US2] Implement the SPA fallback view in `backend/weather/views.py` and register it last in `backend/config/urls.py`, serving `index.html` for non-API, non-static paths and never for `/ws/` or `/health/`
- [X] T047 [US2] Configure WhiteNoise in `backend/config/settings.py` to serve hashed assets from the collected SPA build with compression and immutable cache headers
- [X] T048 [US2] Finalize the `backend` service in `docker-compose.yml`: depends on `postgres` and `redis` being healthy and the `frontend` build completing successfully, mounts `spa_dist` read-only, publishes port `${BACKEND_PORT:-8000}:8000`, and defines a health check hitting `/health/`
- [X] T049 [US2] Finalize the one-shot `frontend` service in `docker-compose.yml` writing to the `spa_dist` volume and writing a build-complete marker consumed by the backend startup
- [X] T050 [US2] Add `worker` and `beat` services to `docker-compose.yml` reusing the backend image with Celery commands, Redis dependency and restart policy
- [X] T051 [US2] Make `backend/entrypoint.sh` idempotent: migrations and `collectstatic` may run on every start, a missing SPA marker fails with a clear message instead of serving a blank page, and the process is replaced with `exec` for clean signals
- [X] T052 [US2] Implement degraded startup in `backend/config/settings.py` and the provider client: an empty `OPENWEATHER_API_KEY` boots normally, health reports `provider_configured: false`, and refresh returns stored data marked stale
- [X] T053 [US2] Add `.dockerignore` files for `backend/` and `frontend/`, and document the one-command startup, optional `.env`, and port override in `README.md`
- [X] T054 [US2] Run the clean-start validation: `docker compose down -v` (explicitly destructive), `docker compose up`, then `scripts/verify-startup.sh`; confirm a second `up` preserves rows

**Checkpoint**: The delivery boots from a clean checkout and survives restarts.

---

## Phase 5: User Story 3 - Explore the stored history of both cities (Priority: P2)

**Goal**: Time-series charts for both cities over 24 h/7 d/30 d and a server-paginated,
city-filtered table, with state mirrored in the URL and consistent totals across views.

**Independent Test**: With stored rows for two cities, switch windows, filter by one city, page
forward and back, and request an out-of-range page; charts and table must stay consistent with
stored data and show an empty state rather than an error.

### Tests for User Story 3 ⚠️

- [X] T055 [P] [US3] Contract test for `GET /weather/` in `backend/weather/tests/contract/test_weather_list.py`: default page size 20, maximum 100, `page` echoes, `total_pages` correct, `city` filter exact and case-insensitive, `start`/`end` bounds, invalid ranges return 400 `invalid_range`, invalid page returns 400 `invalid_pagination`
- [X] T056 [P] [US3] Integration test for series bucketing in `backend/weather/tests/integration/test_series.py`: 15-minute buckets for 24h, 2-hour for 7d, 12-hour for 30d, averages match fixtures, and empty buckets are omitted rather than zero-filled
- [X] T057 [P] [US3] Component test for the table in `frontend/src/components/ObservationsTable.test.tsx`: server pagination calls, page-size change, city filter, URL synchronization, and out-of-range empty state
- [X] T058 [P] [US3] Component test for charts in `frontend/src/components/HistoryCharts.test.tsx`: both series rendered, window switch refetches with the new window, and gaps render as gaps

### Implementation for User Story 3

- [X] T059 [US3] Implement the list view `GET /weather/` in `backend/weather/views.py` using the shared paginator and filter parsing, with `select_related`-free projection of only the documented fields and no N+1 queries
- [X] T060 [US3] Implement the series aggregation service in `backend/weather/services/series.py` using database `date_trunc` bucketing, per-window bucket selection, and omission of empty buckets
- [X] T061 [US3] Extend the dashboard payload in `backend/weather/services/dashboard.py` and `backend/weather/serializers.py` with `series` and `bucket`, cached under the documented series keys with version invalidation
- [X] T062 [US3] Verify the three indexes from `data-model.md` exist in `backend/weather/migrations/` and add a follow-up migration only if any are missing; capture `EXPLAIN` output for the filtered-page and latest-row queries
- [X] T063 [US3] Implement `frontend/src/components/ObservationsTable.tsx` with Ant Design Table server pagination, page-size selector, city filter, newest-first ordering, total display, and URL-synchronized state
- [X] T064 [US3] Implement `frontend/src/components/HistoryCharts.tsx` with Recharts, dual-city series on a shared time axis, a 24h/7d/30d selector, and a responsive container
- [X] T065 [US3] Add loading skeletons, distinct empty states for "no history yet" versus "no rows match this filter", error retry, and a horizontal scroll wrapper for the table below 576 px in `frontend/src/components/HistoryCharts.tsx` and `frontend/src/components/ObservationsTable.tsx`
- [X] T066 [US3] Run the US3 test subsets (`backend/weather/tests/contract/test_weather_list.py`, `backend/weather/tests/integration/test_series.py`, `frontend/src/components/ObservationsTable.test.tsx`, `frontend/src/components/HistoryCharts.test.tsx`) and fix failures

**Checkpoint**: History exploration works independently of live updates and export.

---

## Phase 6: User Story 4 - See new observations arrive without refreshing (Priority: P2)

**Goal**: New observations are persisted by scheduled and on-demand refreshes and pushed to open
dashboards over WebSocket, with visible connection state, deduplication, and automatic recovery.

**Independent Test**: Keep the dashboard open, trigger `POST /weather/refresh/`, and confirm the
comparison, chart and table update within 5 seconds without a reload; stop Redis, confirm the
paused indicator, restart it, and confirm recovery without duplicates.

### Tests for User Story 4 ⚠️

- [X] T067 [P] [US4] Contract test for `/ws/weather/` in `backend/weather/tests/contract/test_websocket.py` using `WebsocketCommunicator`: `snapshot` on connect, `observation` after insert, `heartbeat` shape, and close code 4001 with an `error` frame for duplicate, missing or unknown cities
- [X] T068 [P] [US4] Integration test for fan-out in `backend/weather/tests/integration/test_realtime.py`: an event is emitted only after commit, a rolled-back insert emits nothing, and only subscribed city groups receive the event
- [X] T069 [P] [US4] Integration test for scheduled refresh in `backend/weather/tests/integration/test_tasks.py`: the task selects at most 10 cities seen in the last 24 hours, skips cities with no recent activity, and tolerates provider errors per city without aborting the batch
- [X] T070 [P] [US4] Hook test for the socket client in `frontend/src/ws/useWeatherSocket.test.tsx`: exponential backoff with jitter, deduplication by `(city_key, timestamp)`, stale-frame ignoring, and recovery after reconnect

### Implementation for User Story 4

- [X] T071 [US4] Implement `WeatherConsumer` in `backend/weather/consumers.py` and `backend/weather/routing.py`, wiring `ws/weather/` into `backend/config/asgi.py`
- [X] T072 [US4] Implement subscription handling in `backend/weather/consumers.py`: validate and normalize the two cities, join `weather.{city_key}` per city, send a `snapshot` with the current dashboard payload, emit a `heartbeat` every 25 seconds, answer `ping`, and reject client-authored messages other than `ping`
- [X] T073 [US4] Implement `backend/weather/signals.py` registered from `backend/weather/apps.py`: on `post_save` for an inserted row, use `transaction.on_commit` to serialize the observation with `ObservationSerializer` and `group_send` it to each city group
- [X] T074 [US4] Implement `backend/weather/tasks.py` with `refresh_tracked_cities` and add a 60-second beat entry in `backend/config/celery.py`; bound the batch to 10 cities and reuse the provider, insert, cache-invalidation and fan-out path
- [X] T075 [US4] Implement `frontend/src/ws/useWeatherSocket.ts` with query-parameter subscription, 1–30 second exponential backoff plus 20% jitter, 10-second stability reset, 60-second dead-connection detection, and a `snapshot`-replaces-state strategy
- [X] T076 [US4] Implement `frontend/src/components/ConnectionBadge.tsx` showing live, paused and reconnecting states with accessible text and no color-only signaling
- [X] T077 [US4] Integrate socket events with TanStack Query in `frontend/src/hooks/useDashboardData.ts`: merge or invalidate on `observation`, replace on `snapshot`, and refresh the table page when the new row belongs to the current filter
- [X] T078 [US4] Add `aria-live="polite"` announcements for new observations and connection changes in `frontend/src/components/ConnectionBadge.tsx` and `frontend/src/components/CurrentComparison.tsx`, without announcing every heartbeat
- [X] T079 [US4] Run the US4 test subsets (`backend/weather/tests/contract/test_websocket.py`, `backend/weather/tests/integration/test_realtime.py`, `backend/weather/tests/integration/test_tasks.py`, `frontend/src/ws/useWeatherSocket.test.tsx`) and fix failures

**Checkpoint**: Live updates work end to end and degrade visibly, not silently.

---

## Phase 7: User Story 5 - Export the filtered history to CSV (Priority: P3)

**Goal**: Download a CSV containing exactly the observations matching the active city filter and
window, with correct quoting, formula neutralization, and an empty-export message.

**Independent Test**: Apply a city filter and window, export, open the file in a spreadsheet tool,
and confirm the header, row set and escaping; export with no matches and confirm a header-only
file plus a notice.

### Tests for User Story 5 ⚠️

- [X] T080 [P] [US5] Contract test for `GET /weather/export/` in `backend/weather/tests/contract/test_export.py`: attachment header, header row column order `id,city,country_code,temperature_c,humidity_pct,wind_speed_ms,timestamp`, filter and window applied, pagination ignored, and 400 for invalid ranges
- [X] T081 [P] [US5] Unit test for CSV escaping in `backend/weather/tests/unit/test_csv.py`: commas, quotes and newlines are quoted per RFC 4180 and leading `=`, `+`, `-` and `@` are prefixed with a single quote
- [X] T082 [P] [US5] Component test for the export control in `frontend/src/components/ExportButton.test.tsx`: it sends the active city and window, shows a download state, and displays an empty-export notice on a header-only response

### Implementation for User Story 5

- [X] T083 [US5] Implement the CSV encoder in `backend/weather/services/csv_export.py` with RFC 4180 quoting, formula-injection prefixing, ISO 8601 UTC timestamps, and a streaming row iterator over a values queryset
- [X] T084 [US5] Implement `GET /weather/export/` in `backend/weather/views.py` using `StreamingHttpResponse`, the shared filter parsing, a `Content-Disposition` filename, and the export throttle
- [X] T085 [US5] Implement `frontend/src/components/ExportButton.tsx` in the dashboard toolbar, passing the current filter and window, handling the download, and showing an empty-export notification when the response contains only the header
- [X] T086 [US5] Add an integration test in `backend/weather/tests/integration/test_export_volume.py` seeding 10,000 rows and asserting the export completes under 10 seconds with a constant memory profile
- [X] T087 [US5] Run the US5 test subsets (`backend/weather/tests/contract/test_export.py`, `backend/weather/tests/unit/test_csv.py`, `backend/weather/tests/integration/test_export_volume.py`, `frontend/src/components/ExportButton.test.tsx`) and fix failures

**Checkpoint**: All five stories are independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Compliance, responsiveness, security, performance, documentation and the final
clean-checkout proof.

- [X] T088 [P] Responsive audit at 360 px, 768 px and desktop in `frontend/src/pages/Dashboard.tsx` and region components; fix stacking, overflow and chart-label density
- [X] T089 [P] Accessibility audit in `frontend/src/components/`: labels, focus order, keyboard operation of city search and pagination, contrast, and live-region correctness
- [X] T090 [P] Security hardening in `backend/config/settings.py` and tests: CSP, `nosniff`, `Referrer-Policy`, same-origin enforcement on refresh, throttle verification, and a test proving no provider key appears in responses or logs
- [X] T091 [P] Performance pass: assert a constant query count for `/dashboard-data/`, review `EXPLAIN` for list and series queries, and record measured latencies against the plan's targets in `docs/performance.md`
- [X] T092 [P] Write `README.md` run instructions and `docs/architecture.md` with the data-flow diagram, cache key/TTL table, and error taxonomy
- [X] T093 Verify the implementation matches `contracts/openapi.yaml` and `contracts/websocket.md`; update the contracts for any justified drift
- [X] T094 Run `docker compose exec backend pytest -q`, `docker compose exec backend ruff check .`, `docker compose exec backend mypy weather config`, `docker compose run --rm frontend npm test -- --run`, and `docker compose run --rm frontend npm run typecheck` from the repository root, covering `backend/` and `frontend/`; all must pass
- [X] T095 Execute quickstart scenarios V1–V7 and record pass/fail evidence in `specs/001-weather-comparison-dashboard/quickstart.md` under a "Validation results" heading
- [X] T096 Perform the final clean-checkout proof: `docker compose down -v`, `docker compose up`, `scripts/verify-startup.sh`, one comparison, one export, one live-update check
- [X] T097 Review constitution principles I–VI against the delivered code in `backend/`, `frontend/` and `docker-compose.yml`, and record the compliance notes in the feature pull-request description

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on T001–T011; blocks every user story.
- **User Story 1 (Phase 3)**: Depends on Phase 2. Delivers the MVP.
- **User Story 2 (Phase 4)**: Depends on Phase 2; functionally overlaps Setup's Compose skeleton
  but must be validated after US1 exists so the startup proof can load a comparison.
- **User Story 3 (Phase 5)**: Depends on Phase 2 and benefits from US1's dashboard payload.
- **User Story 4 (Phase 6)**: Depends on Phase 2; its fan-out reuses the US1 insert path, so
  sequence it after US1.
- **User Story 5 (Phase 7)**: Depends on Phase 2; reuses the US3 filter parsing and the US1
  dashboard toolbar.
- **Polish (Phase 8)**: Depends on all completed stories.

### Story Completion Order

`Setup → Foundational → US1 → US2 → US3 → US4 → US5 → Polish`

US3, US4 and US5 are mutually independent after US1 and may run in parallel with separate owners.
US2 is a release gate and SHOULD be completed before external delivery even though US3–US5 can be
developed concurrently.

### Within Each Story

- Test tasks are written first and must fail before implementation.
- Models/services precede views; views precede frontend integration.
- A story is complete only when its test subset passes and its checkpoint is demonstrated.

---

## Parallel Execution Examples

### User Story 1

```bash
# Tests in parallel (different files):
Task: "Contract test GET /dashboard-data/ in backend/weather/tests/contract/test_dashboard_data.py"
Task: "Contract test POST /weather/refresh/ in backend/weather/tests/contract/test_refresh.py"
Task: "Component test CitySelector in frontend/src/components/CitySelector.test.tsx"

# Then implementation in dependency order:
Task: "Dashboard assembly service in backend/weather/services/dashboard.py"
Task: "GET /dashboard-data/ in backend/weather/views.py"
Task: "Typed API client in frontend/src/api/client.ts"
```

### User Story 3

```bash
Task: "Contract test GET /weather/ in backend/weather/tests/contract/test_weather_list.py"
Task: "Integration test series bucketing in backend/weather/tests/integration/test_series.py"
Task: "Component test ObservationsTable in frontend/src/components/ObservationsTable.test.tsx"
Task: "Component test HistoryCharts in frontend/src/components/HistoryCharts.test.tsx"
```

### User Story 4

```bash
Task: "WebSocket contract test in backend/weather/tests/contract/test_websocket.py"
Task: "Fan-out integration test in backend/weather/tests/integration/test_realtime.py"
Task: "Scheduled refresh test in backend/weather/tests/integration/test_tasks.py"
Task: "Socket hook test in frontend/src/ws/useWeatherSocket.test.tsx"
```

### Across Stories (after Phase 2)

```bash
# Three owners, no shared files:
Owner A: Phase 5 (US3 history)
Owner B: Phase 6 (US4 realtime)
Owner C: Phase 7 (US5 export)
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1 and Phase 2.
2. Complete US1 (compare two cities).
3. Complete US2 (single-command startup) — without it the MVP cannot be demonstrated as required.
4. **STOP and VALIDATE**: run `scripts/verify-startup.sh` and manual scenario V1.
5. Demo.

### Incremental Delivery

1. Foundation ready → nothing user-visible yet.
2. US1 → comparison works against live/stored data.
3. US2 → one-command startup and restart durability proven.
4. US3 → history charts and paginated table.
5. US4 → live push and reconnection.
6. US5 → CSV export.
7. Polish → compliance evidence, performance and documentation.

### Notes

- `[P]` marks tasks that touch different files and have no incomplete dependency.
- Every user story is independently testable; do not defer a story's tests to the polish phase.
- Commit after each task or small logical group; never mix two stories in one commit.
- Do not add authentication, unit switching, alerting, or the agent chat in this feature.
- Any scope change requires a microspec amendment before implementation.
