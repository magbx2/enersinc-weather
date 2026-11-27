> **Historical snapshot.** The current compliance review is
> [../../docs/constitution-compliance.md](../../docs/constitution-compliance.md). This copy predates
> constitution v1.2.0 and is kept only for reference.

# Constitution compliance review

Reviewed against `.specify/memory/constitution.md` v1.1.0 for the delivered code in `backend/`,
`frontend/` and `docker-compose.yml`.

| Principle | Status | Evidence |
|---|---|---|
| I. Microspec-first, English-only | PASS | One capability in `specs/001-weather-comparison-dashboard/`; all artifacts, code, UI copy and tests are English |
| II. Layered data flow, one direction | PASS | Browser calls only same-origin Django routes; provider credential stays server-side; live updates only via `/ws/weather/` |
| III. Cache is a contract | PASS | Deterministic keys and TTLs in `weather/cache.py`; all Redis failures logged as `cache_error` and treated as misses; version-key invalidation without key scans |
| IV. Resilience and truthful data | PASS | Provider failures fall back to stored rows marked stale with a `reason`; `no_data_available` instead of fabricated values; failure classes logged separately |
| V. Typed contracts and input validation | PASS | DRF serializers and shared filter parsing; bounded pagination; ORM-only queries; JSON + same-origin refresh; CSP and CSV formula neutralization |
| VI. One-command startup | PASS | `docker compose up` from a clean checkout; health-checked dependencies; migrations, static collection and SPA build handled automatically; named volumes preserve data |

## Notes

- No authentication is implemented by design; the absence of cookie-based state changes is why
  CSRF tokens are not applicable, and same-origin enforcement is documented in the architecture.
- Two extra services (`worker`, `beat`) and one one-shot build service are the only deliberate
  expansions beyond the four required services; rationale is recorded in `plan.md`.
- `./scripts/verify-startup.sh` validates health, the SPA shell and a JSON API route without
  manual steps.
