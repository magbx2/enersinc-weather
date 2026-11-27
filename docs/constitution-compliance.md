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

## Weather Data Chat (spec 002)

Reviewed against the same constitution for `specs/002-weather-data-chat/`.

| Principle | Status | Evidence |
|---|---|---|
| I. Microspec-First, English Artifacts, Spanish UX | PASS | Single capability in `specs/002-weather-data-chat/`; plan, research, data model, contracts, tasks and code are English; the FAB, Drawer, status, empty and failure copy are Spanish and assistant answers are instructed to be Spanish |
| II. Layered Data Flow, One Direction | PASS | SPA posts only to `/chat/messages/`; Django calls LiteLLM server-side with `LLM_*` settings; the browser never contacts a provider |
| III. Cache is a contract | PASS | Chat reads bypass Redis and add no key; the existing TTL table is unchanged |
| IV. Resilience and truthful data | PASS | Tools return `no_data`/`sample_count`; aggregates use ORM `Avg`/`Min`/`Max`; `llm_not_configured` and `llm_unavailable` are visible without leaking provider details |
| V. Typed contracts and input validation | PASS | `ChatRequestSerializer`; UUID session ids; bounded message/limit/dates; enum metric/statistic; ORM-only tools; JSON + same-origin POST; sanitized tool args/output; contracts in `contracts/` |
| VI. One-command startup | PASS | No new service; `litellm` is in the backend image; migrations run in the existing entrypoint; an empty LLM key degrades only the chat |

- Chat persistence is server-side (`ChatSession`, `ChatMessage`, `ToolRun`); the client stores only
  the non-authentication session UUID in `localStorage`.
- `.env.example` documents `LLM_MODEL` and friends with empty/placeholder values and no real keys.
- Verified gates: backend `pytest` (133 passed), `ruff`, `mypy`, migration check; frontend
  `vitest` (38 passed), `tsc --noEmit` and `eslint`.
