# Constitution compliance review

Reviewed against `.specify/memory/constitution.md` v1.2.0 for the delivered code in `backend/`,
`frontend/`, `docker-compose.yml` and the workflow artifacts in `specs/`.

| Principle | Status | Evidence |
|---|---|---|
| I. Microspec-First, English Artifacts, Spanish UX | PASS | One capability in `specs/001-weather-comparison-dashboard/`; specs, plan, tasks, contracts, code identifiers, tests and developer docs are English; `frontend/index.html` declares `lang="es"`, Ant Design uses the `es_ES` locale, all UI-authored copy is Spanish, and English API messages appear only as technical detail within Spanish alerts |
| II. Layered Data Flow, One Direction | PASS | Browser calls only same-origin Django routes; provider credential stays server-side; city search resolves Redis -> PostgreSQL -> OpenWeather; `/dashboard-data/` without a pair reads the latest stored pair; live updates only via `/ws/weather/` with hashed channel groups |
| III. Cache is a contract | PASS | Deterministic keys and TTLs in `weather/cache.py`; `weather:current` cache-aside for per-city reads; all Redis failures logged as `cache_error` and treated as misses; version-key invalidation without key scans |
| IV. Resilience and truthful data | PASS | Provider failures fall back to stored rows marked stale with a `reason`; `no_data_available` instead of fabricated values; empty chart buckets are omitted; a page past the end returns 200 with an empty set; failure classes are logged separately |
| V. Typed contracts and input validation | PASS | DRF serializers and shared filter parsing; bounded pagination; ORM-only queries; JSON + same-origin refresh; CSP and CSV formula neutralization; export accepts `Accept: text/csv`; channel payloads are JSON primitives |
| VI. One-command startup | PASS | `docker compose up` from a clean checkout; health-checked dependencies; migrations, static collection and SPA build handled automatically; named volumes preserve data |

## Notes

- No authentication is implemented by design; the absence of cookie-based state changes is why
  CSRF tokens are not applicable, and same-origin enforcement is documented in the architecture.
- The required baseline is four services (`postgres`, `redis`, `backend`, one-shot `frontend`).
  `worker` and `beat` are the only deliberate extras; rationale is recorded in `plan.md`.
- `./scripts/verify-startup.sh` validates health, the SPA shell and a JSON API route without
  manual steps.
- The implementation records the post-delivery fixes (default stored pair, city-search order,
  hashed channel groups, JSON channel payloads, Redis pin, CSV negotiation, out-of-range pages and
  Spanish UX) in `plan.md` and `tasks.md`.
