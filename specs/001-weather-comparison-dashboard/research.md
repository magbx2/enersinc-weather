# Phase 0 Research: Two-City Weather Comparison Dashboard

All unknowns from the technical context are resolved below. No `NEEDS CLARIFICATION` items remain.

## R1. Runtime, framework and library versions

**Decision**: Python 3.12, Django 5.1, DRF 3.15, Channels 4 with `channels-redis`, Daphne as the ASGI
server, psycopg 3, Redis 7, PostgreSQL 16. Frontend: Node 20, TypeScript 5.6, React 18, Vite 5,
Ant Design 5, TanStack Query 5, Recharts 2, React Router 6.

**Rationale**: These are the current stable lines for the constitution's fixed stack. Daphne serves
HTTP and WebSocket on one port, which keeps the SPA, REST API, and live updates on a single origin.
TanStack Query gives cache-aware fetching, request deduplication, and pagination state without a
custom store. Recharts composes cleanly with Ant Design's layout and supports shared-axis dual
series.

**Alternatives considered**: Gunicorn + separate Channels process (two ports, extra proxy);
Uvicorn workers (workable, but Daphne is the Channels-native reference server); Redux Toolkit
(unnecessary state surface for four regions); Ant Design Charts (heavier bundle, less control over
dual-series tooltips); Nivo or Chart.js (viable, but Recharts has the smallest integration cost).

## R2. External provider integration and error taxonomy

**Decision**: Use OpenWeather Geocoding `/geo/1.0/direct` for city resolution and Current Weather
`/data/2.5/weather` with `units=metric` for observations. Resolve each city to a provider candidate
(id, latitude/longitude, country code) before fetching the reading; persist the display name,
normalized `city_key` and country code, while the numeric provider id remains search-only. Apply a
5-second connect/read timeout, at most 2 retries with exponential backoff on 429/5xx/network errors,
and no retry on 401/403/404. City search resolves through Redis, then PostgreSQL, then the provider,
so stored cities remain available in degraded mode.

Error classes mapped to behavior:

| Provider outcome | System behavior | Client signal |
|---|---|---|
| 200 with body | Store observation, invalidate cache, emit event | `source: "live"` |
| 401/403 invalid credential | Skip provider permanently for the request, fall back to DB | `source: "stale"`, reason `credential_invalid` |
| 404 unknown city | Validation error, no row written | 400 with `code: "unknown_city"` |
| 429 rate limited | One retry after backoff, then DB fallback | `source: "stale"`, reason `rate_limited` |
| 5xx / timeout / connection error | Retry, then DB fallback | `source: "stale"`, reason `provider_unavailable` |
| No DB rows and provider down | No value shown | 503 with `code: "no_data_available"` |

**Rationale**: Explicit classes prevent a single catch-all from masking credential problems as
outages, and they satisfy the requirement that logs distinguish failure origins. Resolving cities
first avoids storing ambiguous names and gives a stable deduplication key.

**Alternatives considered**: One Call API (needs a paid tier for history and adds fields the model
does not use); geocoding by name only per request (duplicate cities across countries); unbounded
retries (amplifies an outage); storing raw provider payloads in `WeatherData` (unneeded scope,
larger rows).

## R3. Cache strategy, keys and TTLs

**Decision**: Cache-aside over Redis with `django-redis`, deterministic keys, explicit TTLs, and
O(1) invalidation through a per-city version counter.

| Key | Contents | TTL | Invalidation |
|---|---|---|---|
| `weather:current:v1:{city_key}` | Latest observation for a city | 60 s | Deleted on insert for that city |
| `weather:dashboard:v1:{city_a}:{city_b}:{window}` | Assembled dashboard payload (current + series + summary) | 30 s | Deleted for both cities on insert |
| `weather:series:v1:{city_key}:{window}:{version}` | Bucketed time series | 60 s | Version counter `weather:seriesver:v1:{city_key}` incremented on insert |
| `geo:search:v1:{query_hash}` | Provider geocoding results | 24 h | Not invalidated (reference data) |
| `geo:invalid:v1:{query_hash}` | Negative result for unknown city | 10 min | Expires |

Implementation rules:

- Serialize with compact JSON and store byte strings; never pickle untrusted values.
- Cache failures (connection error, timeout) are caught, logged at WARNING with `event=cache_error`,
  and treated as a miss. A failed cache read never fails a request.
- Current-condition reads MUST NOT return data older than 60 s without marking it stale; the cache
  TTL equals the freshness window, so a hit is fresh by construction.
- Writes happen after the database transaction commits (`transaction.on_commit`) so cache and
  WebSocket state never describe a rolled-back row.

**Rationale**: 60 s matches the spec's documented freshness window and the automatic refresh
interval. The version counter avoids `SCAN`/`KEYS` and makes series invalidation cheap and atomic.
Negative caching protects the provider from repeated invalid-city lookups.

**Alternatives considered**: Redis-only storage (violates persistence requirement); write-through
cache (complicates rollback semantics); per-row caching (no reuse); 5-minute TTL (would serve data
older than the stated freshness window).

## R4. Real-time transport and fan-out

**Decision**: Django Channels with `channels-redis` as the group layer. One consumer at
`/ws/weather/` accepts a validated `cities` query parameter (exactly two distinct city keys),
subscribes the connection to `weather.<sha256(city_key)[:32]>` per city (via
`weather.realtime.channel_group`), and emits:

- `snapshot` on connect, containing the current dashboard payload so the client renders immediately;
- `observation` when a row is inserted, containing the observation and its source;
- `heartbeat` every 25 s so the client can detect a dead connection;
- `error` with a stable code for invalid subscriptions.

Fan-out is triggered from a `post_save` signal wrapped in `transaction.on_commit`, serialized by the
same serializer used by the REST API. The consumer rejects unauthenticated writes: it accepts no
client messages other than `ping`.

**Rationale**: Per-city groups keep fan-out proportional to interested clients, and the snapshot
message removes the initial fetch/render race. Heartbeats let the UI distinguish "no new data" from
"connection lost".

**Alternatives considered**: One global broadcast group (every client receives irrelevant events);
Server-Sent Events (unidirectional, but no first-class Django Channels integration and no shared
group layer); client polling only (does not meet the under-5-second update criterion).

## R5. Serving the SPA from the Django root

**Decision**: A dedicated `frontend` Compose service builds the Vite app into a named volume
(`spa_dist`). The backend mounts that volume read-only, collects the assets into its static
directory at startup, and Django serves `index.html` for any non-API, non-static route. WhiteNoise
serves hashed assets with compression and long-lived cache headers. The backend depends on the
frontend service with `condition: service_completed_successfully`.

**Rationale**: This preserves the required `frontend` service while guaranteeing a single origin
for SPA, REST, and WebSocket traffic, and it removes CORS entirely. A one-shot build service is the
simplest way to produce immutable assets exactly once per `up`.

**Alternatives considered**: Vite dev server proxied by Django (two runtimes, HMR-only, not a
delivery build); embedding the build in the backend Dockerfile (removes the required service);
Nginx serving the SPA and proxying Django (splits origins and adds a fifth runtime).

## R6. Pagination, filtering and query efficiency

**Decision**: DRF `PageNumberPagination` with `page_size` default 20 and maximum 100, ordered by
`-timestamp`. Filters: `city` (case-insensitive exact on `city_key`), `start`, `end` (ISO 8601,
validated, `start <= end`), and `window` for the dashboard (`24h`, `7d`, `30d`). The table's page,
page size, city filter, and window are mirrored in the URL query string so reloads and shares
preserve state.

Indexes: `(city_key, -timestamp)` for filtered history; a partial ordering index on `-timestamp`
for the unfiltered table. The dashboard endpoint uses one aggregate query per city for bucketed
series (`date_trunc`) plus one latest-row lookup per city, both index-covered.

**Rationale**: Offset pagination is adequate for a single-tenant read-mostly dataset and keeps the
UI contract simple. The composite index matches the only hot filter-plus-sort pair. Bounded
`page_size` satisfies the input-safety requirement and prevents unbounded payloads.

**Alternatives considered**: Cursor pagination (better at scale, but incompatible with "jump to
page" UI); client-side pagination (violates the backend pagination requirement); unbounded export
via the list endpoint (streamed CSV endpoint already covers it).

## R7. CSV export

**Decision**: Stream rows from a server-side iterator with `StreamingHttpResponse`, one header row,
ISO 8601 UTC timestamps, and RFC 4180 quoting. Neutralize spreadsheet formula injection by
prefixing cell values that start with `=`, `+`, `-`, or `@` with a single quote. Export honors the
active `city`, `start`, `end`, and `window`, independent of the current page.

**Rationale**: Streaming keeps memory flat for 10,000+ rows and meets the export time target.
Formula neutralization closes a real injection path that plain CSV quoting does not address.

**Alternatives considered**: Building the CSV in memory (memory grows with history); exporting only
the current page (contradicts the spec's filtered-set semantics); Excel `.xlsx` (extra dependency,
no requirement).

## R8. Scheduling: Celery beat and worker

**Decision**: Include Celery with Redis as broker. Beat runs `refresh_tracked_cities` every 60 s;
the task selects up to 10 city keys with observations in the last 24 h, refreshes each through the
same provider service, and relies on the insert path for cache invalidation and WebSocket fan-out.
A second task, `prune_orphaned_cache_keys`, is not created; TTLs handle expiry. Worker and beat run
as separate Compose services reusing the backend image.

**Rationale**: Unattended ingestion keeps history meaningful and satisfies live updates without a
browser initiating a request. Restricting to recently active cities bounds provider usage. Reusing
the backend image keeps one build artifact.

**Alternatives considered**: Django management command loop in the backend container (no retry or
supervision semantics, competes with the web process); APScheduler inside Daphne (duplicate timers
under multiple workers); no scheduler (history only grows while a dashboard is open).

## R9. Time handling

**Decision**: Store and transmit UTC with `USE_TZ=True`; serialize as ISO 8601 with `Z`. Reject
observations whose provider timestamp is more than 10 minutes in the future or older than 24 h
(clock-skew and replay guards). Format in the browser using the user's locale and time zone; label
the time zone in charts and the table header.

**Rationale**: A comparison of two cities can span time zones; UTC storage prevents ordering bugs
and ambiguous daylight-saving transitions. Client-side formatting keeps the server locale-neutral.

**Alternatives considered**: Store in the city's local time (ambiguous and unorderable across
cities); store naive datetimes (Django warns and comparisons break across DST).

## R10. Security without authentication

**Decision**: Treat every request as untrusted input. City names are trimmed, length-bounded to 80
characters, restricted to letters, spaces, hyphens, apostrophes and periods, and resolved through
the provider rather than interpolated into URLs. All database access uses the ORM; no raw SQL
string construction. JSON-only mutating endpoints require `Content-Type: application/json` and an
`Origin`/`Sec-Fetch-Site` same-origin check; no session or cookie authentication is enabled, so
CSRF tokens are not applicable, and this is documented rather than silently omitted. Responses set
`X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, and a minimal CSP allowing only
self-hosted scripts and styles. Provider keys never appear in responses, logs, or client bundles.
DRF throttling limits refresh and export endpoints per IP.

**Rationale**: With no accounts, the realistic threats are injection, resource abuse, and
credential leakage, not session hijacking. Same-origin checks and JSON-only writes prevent
cross-site request forgery against the refresh endpoint without inventing an auth system.

**Alternatives considered**: Session auth plus CSRF tokens (contradicts "no authentication" scope);
API keys for the browser (leaks the credential); permissive CORS (unnecessary with one origin).

## R11. Testing strategy

**Decision**:

- Unit: provider error mapping, cache key construction, CSV cell neutralization, serializer
  validation, bucket selection.
- Integration: cache hit/miss/unavailable, provider fallback to DB, pagination boundaries, city
  filter, export content, `transaction.on_commit` fan-out, dashboard aggregation correctness.
- Contract: every endpoint and error code in `contracts/openapi.yaml` exercised, WebSocket message
  shapes exercised with `WebsocketCommunicator`.
- Frontend: MSW-mocked API for loading, empty, error, stale, and paginated states; WebSocket mock
  for live update, disconnect, and reconnect; responsive assertions at 360 px.

External HTTP is always mocked (`respx`); tests never call OpenWeather. Redis is either an
ephemeral test instance or an in-memory fake; no test depends on a developer's local services.

**Rationale**: This covers each functional requirement with at least one executable check and keeps
CI deterministic and offline.

**Alternatives considered**: Recorded provider cassettes (brittle, secrets risk); end-to-end
browser automation only (slow, poor failure isolation); no frontend tests (would leave loading,
error, and reconnect states unverified).

## R12. Startup, configuration and data persistence

**Decision**: Compose declares `postgres`, `redis`, `frontend`, `backend`, `worker`, `beat`.
Postgres and Redis have health checks; backend waits for both plus successful frontend build.
`entrypoint.sh` runs `manage.py migrate --noinput`, `collectstatic --noinput`, then starts Daphne.
Defaults for every variable are embedded in `docker-compose.yml`, so no `.env` is required;
`.env.example` documents overrides. Named volumes: `pg_data`, `redis_data`, `spa_dist`, `media`.
Redis runs with append-only persistence so cached state and broker messages survive restarts.

**Rationale**: Startup ordering eliminates the classic race where Django runs migrations before
Postgres accepts connections. Defaults satisfy the "no pre-existing configuration file" criterion,
while an empty `OPENWEATHER_API_KEY` exercises the degraded-but-booting path.

**Alternatives considered**: `wait-for-it` polling without health checks (duplicates Compose
semantics); running migrations from a separate one-shot service (adds a service and ordering
complexity); bundling `.env` in the image (secret leakage risk).

## R13. Responsiveness and UI composition

**Decision**: Ant Design `Grid` with a two-column comparison that collapses to one column below
768 px, and a horizontally scrollable table wrapper below 576 px rather than hiding columns.
Charts use a responsive container with a minimum height and hide dense axis labels on narrow
viewports. All four data regions implement explicit loading skeletons, empty states, error
retries, and a stale/degraded badge.

**Rationale**: The comparison is the primary content and must remain side-by-side where space
allows; scrolling a table preserves all data at 360 px, which the spec requires.

**Alternatives considered**: Hiding metrics on mobile (loses information); card carousels (hides one
city's values from simultaneous comparison); fixed-width charts (overflow on mobile).
