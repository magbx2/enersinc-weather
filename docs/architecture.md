# Architecture

## Data flow

The browser talks only to the Django origin. The external provider credential never leaves the
server, and every displayed value comes from a stored `WeatherData` row.

```text
React SPA
  │ GET /dashboard-data/, /weather/, /cities/search/, /weather/export/, /health/
  │ POST /weather/refresh/
  │ WS  /ws/weather/?cities=<a>,<b>
  ▼
Django REST Framework / Channels consumer
  ├─▶ Redis cache (cache-aside, documented TTLs, version-key invalidation)
  ├─▶ PostgreSQL (append-only observations)
  └─▶ OpenWeather geocoding + current weather (5 s timeout, 2 retries)
```

## Default comparison and city search

`GET /dashboard-data/` without `cities` reads PostgreSQL and returns the two cities with the most
recent stored observations (zero or one when history is short), so opening `/` renders whatever is
already stored instead of an empty screen. The SPA then reflects that pair in the URL.

`GET /cities/search/` resolves in the documented order: Redis geocoding cache, PostgreSQL
observations already stored, then OpenWeather geocoding. Free-form `City Country` input is retried
as `City,Country` before reaching the provider. The refresh path still resolves through the provider
because `WeatherData` does not persist latitude/longitude; stored rows are a search convenience, not
a substitute for a live reading.

Scheduled ingestion runs in Celery (`worker` + `beat`). Every insert goes through
`weather.services.observations.persist_observation`, which:
1. deduplicates on `(city_key, timestamp)`;
2. drops `weather:current:v1:{city_key}` and increments the per-city series version;
3. lets the `post_save` receiver fan out over `transaction.on_commit`.

## Cache contract

Redis is mandatory. Every key carries an explicit TTL, and any Redis error is logged as
`event=cache_error` and treated as a miss, so a cache outage never fails a request.

| Key | Contents | TTL |
|---|---|---|
| `weather:current:v1:{city_key}` | Latest stored observation for one city | 60 s |
| `weather:dashboard:v1:{city_a}:{city_b}:{window}` | Assembled dashboard payload plus per-city versions | 30 s |
| `weather:series:v1:{city_key}:{window}:{version}` | Bucketed time series | 60 s |
| `weather:seriesver:v1:{city_key}` | Monotonic version counter | none |
| `geo:search:v1:{query_hash}` | Provider geocoding candidates | 24 h |
| `geo:invalid:v1:{query_hash}` | Negative geocoding result | 10 min |

The dashboard value is wrapped with the current series versions. A mismatch is a cache miss, so
a new insert invalidates every cached dashboard containing that city without scanning keys.

Django's cache version prefix is disabled with `weather.cache.raw_key` so the keys above match
the documentation and the quickstart's `redis-cli` commands exactly.

## Freshness and truthfulness

- `age_seconds = now - observed_at`, clamped at zero.
- `freshness = current` when `age_seconds <= 60`, otherwise `stale`; `unavailable` when no row
  exists.
- A provider failure forces `freshness = stale` even for a recent row, and adds a `reason`
  (`credential_invalid`, `rate_limited`, `provider_unavailable`).
- Derived values (deltas, buckets) are never stored. Empty chart buckets are omitted, not filled
  with zeroes.

## Language boundary

Repository artifacts, API field names, error codes, log events and developer documentation are
English. The dashboard is Spanish: `frontend/index.html` declares `lang="es"`, Ant Design is
configured with the `es_ES` locale, and every UI-authored label, table header, chart title,
empty/error/stale/reconnecting state and accessibility announcement is Spanish. API `message`
strings are developer-facing and may appear only as technical detail within an alert whose UI copy
is Spanish.

## CSV export negotiation

`GET /weather/export/` streams `text/csv` directly. Because the project registers only the JSON
renderer, the view overrides content negotiation so the SPA's `Accept: text/csv` returns HTTP 200
instead of 406. The response sets `Content-Disposition: attachment` and `Cache-Control: no-store`.

## Error taxonomy

Every error uses `{"error": {"code", "message", "details", "request_id"}}`.

| Code | HTTP | Cause |
|---|---|---|
| `invalid_city` | 400 | Empty, too long, markup or unsupported characters |
| `duplicate_city` | 400 | Same city twice after normalization |
| `unknown_city` | 400 | Refresh resolution: provider geocoding returns no candidate; city search returns an empty list instead |
| `invalid_pagination` | 400 | Non-integer page, page below 1, or page size outside 1–100; a page beyond the last page is 200 with empty results |
| `invalid_window` | 400 | Window outside `24h`, `7d`, `30d` |
| `invalid_range` | 400 | Malformed or reversed `start`/`end` |
| `provider_unavailable` | 503 | Fallback path when nothing is stored |
| `credential_invalid` | — | Provider rejected the key; logged and degraded |
| `rate_limited` | 429 | Throttle or provider rate limit |
| `no_data_available` | 503 | No stored rows and no provider |
| `cross_origin_rejected` | 403 | Refresh without a same-origin marker |
| `internal_error` | 500/503 | Storage unavailable or unexpected failure |

Provider, cache and database failures are logged with distinct `event` values:
`provider_failure`, `cache_error`, `database_error`.

## WebSocket protocol

`GET /ws/weather/?cities=<a>,<b>` accepts exactly two distinct, known cities and joins
`weather.<sha256(city_key)[:32]>` per city. The hash makes keys such as `new york` or `o'brien`
valid Channels group names; the consumer and the `post_save` publisher call the same
`weather.realtime.channel_group` helper. Observation payloads are normalized to JSON primitives
before `group_send`, because the channel layer uses msgpack and cannot pack `Decimal`. The server
sends:

- `snapshot` on connect (the full dashboard payload);
- `observation` after a committed insert, with `source: "live"`;
- `heartbeat` every 25 s and in reply to a client `ping`;
- `error` plus close code `4001` for an invalid subscription.

Clients may only send `ping`. The browser deduplicates by `(city_key, timestamp)` and ignores
frames older than the displayed reading. Reconnection uses 1–30 s exponential backoff with 20 %
jitter, resets after 10 s of stability, and treats 60 s without a frame as a dead connection.

## Startup

`docker compose up` starts PostgreSQL and Redis with health checks, runs the one-shot frontend
build into the `spa_dist` volume, then starts the backend. The entrypoint applies migrations,
requires the SPA build marker, collects static assets and `exec`s Daphne for clean signals.
`worker` and `beat` wait for the backend to be healthy, which removes the migration race.

## Security without authentication

No accounts are in scope, so the realistic threats are injection, resource abuse and credential
leakage:

- all inputs are validated before use; all SQL is ORM-generated;
- refresh requires JSON and an `Origin`/`Sec-Fetch-Site` same-origin marker;
- refresh and export are throttled per IP with a `Retry-After` header;
- responses set `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin` and a minimal
  CSP allowing only self-hosted assets;
- the provider key is never logged, cached, returned or bundled into the SPA;
- CSV cells beginning with `=`, `+`, `-` or `@` are prefixed with a single quote.
