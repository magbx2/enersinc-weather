# Quickstart and Validation Guide: Two-City Weather Comparison Dashboard

This guide proves the feature end to end. It describes commands and expected outcomes only; data
shapes live in [data-model.md](./data-model.md), the REST contract in
[contracts/openapi.yaml](./contracts/openapi.yaml), and the live protocol in
[contracts/websocket.md](./contracts/websocket.md).

Repository artifacts, commands and API field names are English. Every visible string authored by the
dashboard is Spanish (`lang="es"`), including labels, empty/error/stale states and notifications;
English API messages may appear only as technical detail within Spanish UI copy.

## Prerequisites

- Docker Engine 24+ with Compose v2.20+ (`docker compose version`).
- At least 2 GB of free memory and port 8000 free.
- No Python, Node, PostgreSQL or Redis installation is required on the host.
- Optional: an OpenWeather API key. Without one the system MUST still start and run in degraded
  mode, which is itself a required validation.

## Start the system

```bash
git clone <repository-url> weather-dashboard
cd weather-dashboard
docker compose up
```

No `.env` file, migration, seed, or build step is performed by hand. The first run builds images,
which takes longer than later runs.

To supply a provider key (optional):

```bash
cp .env.example .env
# set OPENWEATHER_API_KEY in .env
docker compose up
```

### Expected startup outcome

1. `postgres` and `redis` become healthy.
2. `frontend` completes the SPA build and exits successfully.
3. `backend` applies migrations, collects static assets, and starts serving on port 8000.
4. `worker` and `beat` report ready against Redis.

Verify readiness:

```bash
curl -s http://localhost:8000/health/
```

Expected shape (values may differ):

```json
{
  "status": "ok",
  "database": "up",
  "cache": "up",
  "provider_configured": true,
  "scheduler": "up",
  "version": "1.0.0"
}
```

Then open `http://localhost:8000/` — the dashboard is served by Django at the root path.

## Validation scenarios

### V1. Two-city comparison (User Story 1)

1. Open `http://localhost:8000/` with no city pair. If stored observations exist, confirm the two
   cities with the most recent readings load automatically and the URL is updated with them. If no
   rows exist, confirm the Spanish empty state (`Elige dos ciudades para comparar su tiempo.`).
2. Search for and select two distinct cities, for example `Santiago` and `Valparaiso`.
3. Confirm both panels show temperature (°C), humidity (%), wind speed (m/s), the observation
   time, and the signed difference for each metric. Confirm the labels are Spanish
   (`Temperatura`, `Humedad`, `Velocidad del viento`, `Diferencia ...`).
4. Select the same city in both slots and confirm the second selection is rejected with the Spanish
   message `Las dos ciudades deben ser diferentes.`
5. Enter a nonsense city and confirm an explanatory validation message appears and no values are
   shown.
6. Stop the provider or start without a key and search for a city that already has stored
   observations; confirm it still appears in the results.

Expected: values are populated from stored observations, timestamps are shown, and no placeholder
numbers appear for rejected or unknown cities.

### V2. One-command startup (User Story 2)

From a clean checkout with no `.env` and no running containers:

```bash
docker compose up
```

Expected: the dashboard is reachable and the health endpoint answers within one run, with no
additional command. Record the elapsed time from command start to the first successful `/health/`
response; SC-001 requires less than 5 minutes. Then:

```bash
docker compose down
docker compose up
```

Expected: previously stored observations are still present and no setup is repeated. `docker
compose down -v` is the only destructive variant and is not required by normal operation.

### V3. History, pagination and filters (User Story 3)

1. Open the history area after at least a few observations exist.
2. Switch the window between 24h, 7d and 30d and confirm both city series re-render.
3. Use the city filter and confirm the table, its totals, the charts and the export all follow it.
4. Move to the next page and confirm the rows change and `page`/`page_size` appear in the URL.
5. Request a page past the end and confirm an empty state, not an error.

API-level checks:

```bash
curl -s "http://localhost:8000/weather/?page=1&page_size=5" | jq '.count, .page, .total_pages'
curl -s "http://localhost:8000/weather/?city=Santiago&page=1" | jq '.results[0]'
curl -s "http://localhost:8000/dashboard-data/?cities=Santiago,Valparaiso&window=24h" | jq '.cities[].city'
```

Expected: bounded pages, filtered results, and a dashboard payload with exactly two city entries.

### V4. Live updates (User Story 4)

1. Keep the dashboard open with two cities selected.
2. Trigger a refresh for the same pair:

```bash
curl -s -X POST http://localhost:8000/weather/refresh/ \
  -H 'Content-Type: application/json' \
  -H 'Origin: http://localhost:8000' \
  -d '{"cities":["Santiago","Valparaiso"]}'
```

3. Confirm the open dashboard updates without a page reload within 5 seconds.
4. Stop Redis briefly (`docker compose stop redis`) and confirm the UI shows a paused/degraded
   indicator, then restart it and confirm automatic recovery.

Expected: new observations arrive automatically; disconnection is visible, not silent.

### V5. CSV export (User Story 5)

```bash
curl -s -D /tmp/headers.txt \
  -H 'Accept: text/csv' \
  "http://localhost:8000/weather/export/?city=Santiago&window=24h" -o /tmp/weather.csv
head -3 /tmp/weather.csv
grep -i 'content-disposition' /tmp/headers.txt
```

Expected: HTTP 200 even with `Accept: text/csv`, an attachment header, a header row, and rows
matching the filter. A city name containing a comma, quote or newline stays inside one quoted field,
and a leading `=`, `+`, `-` or `@` is prefixed with a single quote.

### V6. Degraded provider (resilience)

Start with an invalid key, or simulate an outage by pointing the provider base URL at an
unreachable host in `.env`:

```bash
OPENWEATHER_API_KEY=invalid docker compose up
```

Expected: startup succeeds, health reports `provider_configured: false` or a provider failure,
the dashboard still shows the last stored readings marked stale, and no value is fabricated. When
no stored data exists, the comparison area shows an explicit "data unavailable" state.

### V7. Cache behavior and TTL

```bash
docker compose exec redis redis-cli --scan --pattern 'weather:*'
docker compose exec redis redis-cli ttl weather:current:v1:santiago
```

Expected: keys follow the documented scheme and the current-condition TTL is 60 seconds or less.
After a new insert, the current key is gone or replaced, and the series version counter has been
incremented.

## V8. Value traceability and latency probe

Traceability audit (SC-006):

1. Pick one dashboard payload: `curl -s "http://localhost:8000/dashboard-data/?cities=Santiago,Valparaiso&window=24h"`.
2. For each city, compare `observed_at`, temperature, humidity and wind speed with the newest row
   returned by `curl -s "http://localhost:8000/weather/?city=<name>&page_size=1"`.
3. Confirm every displayed value matches a stored row and that no delta or bucket exists without a
   source row.

Cached latency probe (SC-003):

```bash
for i in $(seq 1 20); do
  curl -s -o /dev/null -w '%{time_total}\n' \
    "http://localhost:8000/dashboard-data/?cities=Santiago,Valparaiso&window=24h"
done | sort -n | awk '{a[NR]=$1} END {print "p95:", a[int(NR*0.95)]}'
```

Expected: the p95 is under 2 seconds (the recorded development measurement is far lower). Append the
result to [docs/performance.md](../../docs/performance.md).

## Running the automated checks

```bash
# Backend unit, integration and contract tests
docker compose exec backend pytest -q

# Frontend component tests
docker compose run --rm frontend npm test -- --run

# Static analysis and type checks
docker compose exec backend ruff check .
docker compose exec backend mypy weather config
docker compose run --rm frontend npm run typecheck
```

All external provider calls are mocked in tests; the suite must pass with no network access.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Port 8000 already in use | Another process is listening | Stop it or set `BACKEND_PORT=8001` and retry |
| `frontend` service exits non-zero | TypeScript or build error | Run `docker compose run --rm frontend npm run build` and read the output |
| Dashboard loads but assets 404 | SPA volume not populated | Run `docker compose down` then `docker compose up` to rebuild |
| Health shows `cache: down` | Redis not healthy | Inspect `docker compose logs redis`; Redis is required for cache and Channels |
| Every reading is stale | Missing or invalid provider key | Set `OPENWEATHER_API_KEY`; degrade mode is expected without it |
| Charts are sparse | No history accumulated yet | Expected on first run; history grows with each refresh and scheduled poll |
| WebSocket keeps reconnecting | Server restarted or proxy dropped the connection | Confirm `docker compose logs backend`; the client reconnects within 30 s |

## Validation results

Recorded on 2026-11-25 with Docker Engine 29.10 and Compose v5.8 on a clean checkout.
No real `OPENWEATHER_API_KEY` was configured, so live provider paths were exercised through the
automated mocked-provider suites; stored-data paths were exercised against the running stack.

| Scenario | Status | Evidence |
|---|---|---|
| V1. Two-city comparison | PASS | After seeding two stored observations, `GET /dashboard-data/?cities=Santiago,Valparaiso` returned two snapshots, signed deltas `+2.2 / -9 / -2.3`, `warmer_city: Santiago`, observation times and `freshness: current`. `GET /dashboard-data/` without `cities` returns the latest stored pair, and `Dashboard.test.tsx` verifies the URL reflection and the Spanish empty state. Duplicate, unknown and malformed cities are covered by `test_dashboard_data.py`, `test_refresh.py`, `test_city_search.py` and `CitySelector.test.tsx`. |
| V2. One-command startup | PASS | `docker compose down -v` then `docker compose up -d`; `scripts/verify-startup.sh` passed (health, SPA shell, JSON API). A later `docker compose restart backend` and a full `down`/`up` cycle preserved all rows (`count: 2`). |
| V3. History, pagination and filters | PASS | `/weather/?page=1&page_size=5` returned `count=2`, `page=1`, `total_pages=1`; `city` filtering and bounds are covered by `test_weather_list.py`; a page past the end returns HTTP 200 with an empty result set, not an error. |
| V4. Live updates | PASS (automated) | `test_websocket.py` verifies `snapshot`, `observation`, `heartbeat`, ping and close code `4001`, including a city key with a space joining the hashed channel group; `test_realtime.py` verifies JSON primitives and `transaction.on_commit`; `useWeatherSocket.test.tsx` verifies deduplication, stale-frame ignoring and exponential-backoff reconnection. With Redis stopped, the API kept serving stored data and health reported `cache: down` / `scheduler: unknown`; after restart it returned to `cache: up`. |
| V5. CSV export | PASS | `GET /weather/export/?city=Santiago&window=24h` with `Accept: text/csv` returned HTTP 200, `Content-Disposition: attachment; filename="weather-observations.csv"` and a header row plus `1,Santiago,CL,18.40,62,3.10,...`. Quoting, formula neutralization and the `Accept: text/csv` regression are covered by `test_csv.py` and `test_export.py`. |
| V6. Degraded provider | PASS | With no key, the stack booted, `/health/` reported `status: degraded`, `provider_configured: false`; with no stored rows the dashboard returned `503 no_data_available`; with stored rows it returned them marked `stale`. `test_city_search.py` confirms stored cities remain searchable without the provider. No fabricated values appeared. |
| V7. Cache behavior and TTL | PASS | After a dashboard read, `redis-cli --scan --pattern 'weather:*'` showed `weather:current:v1:santiago`, `weather:current:v1:valparaiso`, `weather:dashboard:v1:santiago:valparaiso:24h`, `weather:series:v1:*:24h:1` and `weather:seriesver:v1:*`. `ttl weather:current:v1:santiago` returned 55 s (≤ 60 s), and an insert incremented the series version. |
| V8. Traceability and latency probe | PROCEDURE ADDED | The audit compares every displayed value with the newest stored row; the 20-request probe records p95 against the 2-second target. Run both after the next full stack start and append the result to `docs/performance.md`. |

### Automated checks

```text
docker compose exec backend pytest -q                 all tests passed
docker compose exec backend ruff check .             All checks passed
docker compose exec backend mypy weather config      Success: no issues found in 31 source files
docker compose run --rm frontend npm test -- --run   all tests passed
docker compose run --rm frontend npm run typecheck   passed
docker compose run --rm frontend npm run lint        passed
```

The aggregate counts from the first validation run were 90 backend tests and 30 frontend tests.
The post-delivery fixes add the city-search, channel-group, JSON-primitive, export-negotiation,
default-pair and Spanish-UX tests listed above; re-run the commands to refresh the counts.
