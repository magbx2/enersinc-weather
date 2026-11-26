# Performance notes

Measured on the development machine with the Compose stack (`postgres` and `redis` containers,
Django served by Daphne), 2026-11-25. Numbers are informational; the assertions live in the
automated tests and in the quickstart V8 probes.

| Scenario | Target | Measured | Evidence |
|---|---|---|---|
| Cached dashboard payload | p95 < 500 ms | 4–6 ms (3 sequential requests; p95 probe pending) | `curl -w '%{time_total}'` against `/dashboard-data/`; 20-request probe in quickstart V8 |
| Cold dashboard payload for a new pair | p95 < 2 s | 36 ms | first request for a pair with stored rows, empty cache |
| SQL statements for one dashboard assembly | bounded/constant | 4 (2 latest rows + 2 bucket aggregates) | `weather/tests/integration/test_query_count.py` |
| Second dashboard read within TTL | no repeated queries | 0 SQL statements | same test |
| 10,000-row CSV export | < 10 s | covered by `test_export_volume.py` (streaming, flat memory) | `weather/tests/integration/test_export_volume.py` |
| New observation fan-out | < 5 s | immediate after commit; heartbeat 25 s | `test_realtime.py`, `test_websocket.py` |
| Table page change | < 1 s | single indexed `LIMIT/OFFSET` query | `(city_key, -timestamp)` index |

## Query shape

The dashboard performs:

1. newest row per city — `ORDER BY timestamp DESC LIMIT 1` on `(city_key, timestamp DESC)`;
2. bucketed series per city — one `date_trunc` aggregate filtered by the window.

The list endpoint projects only the documented columns and uses the same composite index for
city-filtered pages and `ix_weather_ts_desc` for unfiltered pages. The export iterates a values
queryset with a chunk size of 2,000 and streams rows, so memory does not grow with history.

## Reproducing

```bash
time curl -s -o /dev/null "http://localhost:8000/dashboard-data/?cities=Santiago,Valparaiso&window=24h"
time curl -s -o /dev/null "http://localhost:8000/weather/?page=1&page_size=20"

# Cached p95 over 20 sequential requests (SC-003)
for i in $(seq 1 20); do
  curl -s -o /dev/null -w '%{time_total}\n' \
    "http://localhost:8000/dashboard-data/?cities=Santiago,Valparaiso&window=24h"
done | sort -n | awk '{a[NR]=$1} END {print "p95:", a[int(NR*0.95)]}'

docker compose exec backend pytest -q \
  weather/tests/integration/test_query_count.py \
  weather/tests/integration/test_export_volume.py --durations=5
```
