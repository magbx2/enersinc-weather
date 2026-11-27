# Two-City Weather Comparison Dashboard Constitution

**Version**: 1.2.0
**Ratified**: 2026-11-25
**Last Amended**: 2026-11-25

<!--
Sync Impact Report
- Version change: 1.1.0 -> 1.2.0 (MINOR: Principle I materially redefined and expanded)
- Modified principles:
  - I. Microspec-First, English-Only -> I. Microspec-First, English Artifacts, Spanish UX
  - II. Layered Data Flow, One Direction (clarified with the implemented search/default-pair flow)
  - III. Cache Is a Contract (clarified per-city current cache and invalidation)
  - IV. Resilience and Truthful Data (clarified degraded, empty and out-of-range behavior)
  - V. Typed Contracts and Input Validation (clarified CSV negotiation and channel-layer payloads)
  - VI. One-Command Startup (clarified required services and volumes)
- Added sections: none
- Removed sections: none
- Follow-up TODOs: none
-->

## Core Principles

### I. Microspec-First, English Artifacts, Spanish UX

Every feature MUST be described by one single-concern microspec under `specs/` before
implementation. Every repository artifact MUST be written in English: specification, plan,
research, data model, contracts, tasks, quickstart, code identifiers, comments, tests, log events,
commit messages, README and developer documentation. Test descriptions and code are English; tests
and specifications MAY quote Spanish UI copy as evidence.

All user-facing copy MUST be written in Spanish and MUST remain consistent across the product:

- page `<title>`, meta description and the document `lang="es"` attribute;
- labels, buttons, table headers, chart titles, legends and tooltips;
- loading, empty, error, stale, degraded and reconnecting states;
- validation messages authored by the interface, notifications and confirmation text;
- accessibility labels, `aria-live` announcements and keyboard-help text.

API vocabulary (`code`, field names, `event` values and JSON keys) remains English because it is a
machine contract. API `message` strings are developer-facing and remain English. Each user-facing
alert or empty state MUST contain Spanish UI-authored copy; API messages MAY appear as technical
detail in an error description or validation message and MUST NOT be the only explanation the user
receives.

**Rationale**: English keeps the codebase, contracts and reviews consistent with the rest of the
tooling. Spanish is the language of the people using the dashboard, so every visible string authored
by the interface must be Spanish and every visible state must have a Spanish explanation.

### II. Layered Data Flow, One Direction

The browser MUST talk only to the same-origin Django application. The provider credential MUST stay
server-side and MUST NEVER be bundled into the SPA, returned by an endpoint or written to a log.

The implemented flow is non-negotiable:

- REST reads: browser -> Django -> Redis cache -> PostgreSQL; OpenWeather is contacted only when a
  refresh is explicitly requested;
- city search: Redis geocoding cache -> PostgreSQL observations -> OpenWeather geocoding;
- refresh: Django -> OpenWeather -> PostgreSQL -> cache invalidation -> Channels fan-out;
- live updates: Django Channels -> `/ws/weather/` -> browser, never a direct provider connection.

`GET /dashboard-data/` without `cities` MUST read the latest stored pair from PostgreSQL (zero, one
or two cities) so opening `/` never invents a comparison. The SPA MUST reflect that pair in the URL.
Channel groups MUST use a Channels-valid, deterministic name derived from the city key
(`weather.<sha256(city_key)[:32]>`), so keys with spaces or apostrophes remain subscribable.

**Rationale**: A single origin and a single server-side access path keep credentials, validation and
truthfulness enforceable. The search and default-pair additions preserve that direction.

### III. Cache Is a Contract

Redis is mandatory. Every key MUST have a documented TTL and a deterministic builder:

| Key | Contents | TTL |
|---|---|---|
| `weather:current:v1:{city_key}` | Latest stored observation for one city | 60 s |
| `weather:dashboard:v1:{city_a}:{city_b}:{window}` | Assembled dashboard payload plus per-city versions | 30 s |
| `weather:series:v1:{city_key}:{window}:{version}` | Bucketed time series | 60 s |
| `weather:seriesver:v1:{city_key}` | Monotonic series version | none |
| `geo:search:v1:{query_hash}` | Provider geocoding candidates | 24 h |
| `geo:invalid:v1:{query_hash}` | Negative geocoding result | 10 min |

Reads MUST be cache-aside. A cache miss, timeout or outage MUST be logged as `event=cache_error`
and treated as a miss, never as a failed request. A new observation MUST invalidate the city's
current entry and rotate its series version. Dashboard entries MUST be invalidated for every
affected city without `KEYS` or `SCAN`.

**Rationale**: The cache is part of the observable contract, not an optional optimization; it keeps
the dashboard fast while PostgreSQL remains the only source of truth.

### IV. Resilience and Truthful Data

The dashboard MUST serve stored data when the provider, the cache or a dependent service fails. A
provider failure MUST fall back to the most recent stored observation, mark it `stale` and record a
`reason` (`credential_invalid`, `rate_limited`, `provider_unavailable`). The system MUST NEVER
invent, interpolate, estimate or zero-fill displayed values or chart buckets.

Every data region MUST define loading, empty, error and degraded states. A page beyond the last page
MUST return `200` with an empty result set, not an error. Opening the product with no stored rows
MUST show an instructive empty state. Logs MUST distinguish `provider_failure`, `cache_error` and
`database_error`.

**Rationale**: Resilience without truthfulness is worse than an honest empty state.

### V. Typed Contracts and Input Validation

Every input MUST be validated at the boundary with serializers, shared parsers or the equivalent
typed contract. User-supplied city names MUST be checked for length, control characters, markup and
unsupported characters before reaching the provider, storage or a cache key. Pagination MUST be
bounded (`page >= 1`, `page_size` 1-100). SQL MUST be ORM-generated. Mutating requests MUST require
JSON and a same-origin marker. CSV output MUST apply RFC 4180 quoting and neutralize leading `=`,
`+`, `-` and `@`.

The REST contract in `contracts/openapi.yaml` and the WebSocket contract in
`contracts/websocket.md` MUST match the implementation. The CSV endpoint MUST accept
`Accept: text/csv` even though the project's default DRF renderer is JSON. WebSocket payloads MUST
contain JSON primitives before they reach the channel layer, so `Decimal` values are converted to
`float` or `str` and messages survive msgpack serialization.

**Rationale**: Typed boundaries are the project's first line of defense and its executable
documentation.

### VI. One-Command Startup

A clean checkout MUST become fully usable with `docker compose up` and zero manual follow-up. The
required baseline is four services: `postgres`, `redis`, `backend` and the one-shot `frontend` build.
`worker` and `beat` are deliberate extras documented in the plan's complexity table; they exist so
history accumulates and live fan-out works without an open browser.

Startup MUST handle migrations, static collection, the SPA build marker and health checks
automatically. Named volumes MUST preserve PostgreSQL, Redis and built SPA data across restarts.
The stack MUST start without `.env` and without a provider key, reporting degraded readiness instead
of failing to boot.

**Rationale**: An evaluator must be able to reproduce the whole product with one command.

## Additional Constraints

- No authentication, roles, multi-user collaboration or accounts are in scope.
- The provider credential is optional; an empty key is a supported degraded mode.
- Units are metric: Celsius for temperature and meters per second for wind speed.
- All timestamps are stored and transported in UTC ISO 8601 and rendered in the user's local zone.
- Current-condition freshness is 60 seconds; history windows are exactly 24 h, 7 d and 30 d.
- Observations are retained indefinitely in this delivery; no purge job is required.
- The agent-based chat over stored history is a separate microspec and is out of scope here.
- Same-name cities in different countries share the name-based `city_key` in this delivery; a
  persisted provider identifier is explicitly deferred.

## Development Workflow

- Each feature starts from a microspec and follows specify -> plan -> tasks -> implement.
- Tests are written first for every user story and MUST pass before the story is considered done.
- The required quality gates are: backend `pytest`, `ruff` and `mypy`; frontend `vitest`,
  `typecheck` and `lint`; and `scripts/verify-startup.sh`.
- Pull requests or delivery notes MUST identify the affected principles and link the evidence.
- The quickstart validation scenarios and `docs/constitution-compliance.md` are the compliance
  record for each delivery.

## Governance

This constitution supersedes local habits and undocumented conventions. Amendments require an
explicit written change, a version bump and a compliance re-check of the affected artifacts.
Versioning follows semantic versioning: MAJOR for removed or redefined principles, MINOR for new
principles or materially expanded guidance, PATCH for clarifications. Every feature review MUST
verify compliance with all six principles; a violation blocks delivery until the code, spec or
constitution is corrected. The constitution is reviewed whenever a principle changes or a feature
introduces a new cross-cutting concern.

**Version**: 1.2.0 | **Ratified**: 2026-11-25 | **Last Amended**: 2026-11-25
