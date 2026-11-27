# Tasks: Two-City Weather Comparison Dashboard

**Generated from feature specification with clarifications integrated**

## Task Organization
- Tasks organized by user story priority (P1 > P2 > P3)
- Setup phase (Phase 1), Foundational prerequisites (Phase 2), User story phases (Phase 3+)
- Final phase: Polish & Cross-Cutting Concerns
- Each task follows checklist format: `- [ ] T### [optional [P]] [optional [USx]] Description with file path`

## Phase Structure
- **Phase 1**: Setup (project initialization)
- **Phase 2**: Foundational (blocking prerequisites - MUST complete before user stories)
- **Phase 3+**: User Stories in priority order (P1, P2, P3...)
- **Final Phase**: Polish & Cross-Cutting Concerns

--- PHASE 1: Setup (project initialization) ---
- [ ] T001 Initialize Django project structure within feature directory
- [ ] T002 Configure Django settings: INSTALLED_APPS, MIDDLEWARE, DATABASES, CACHES per constitution
- [ ] T003 Set up Docker Compose services: postgres, redis, frontend, backend, worker, beat
- [ ] T004 Add constitution principles documentation reference in repository root
- [ ] T005 Configure Django Channels with Redis broker and default channel layer
- [ ] T006 Set up Django migrations directory and initial models per data-model.md
- [ ] T007 [P] Create WeatherData model per data-model.md entity definition

--- PHASE 2: Foundational (blocking prerequisites) ---
- [ ] T008 [P] Create city search service: Redis -> PostgreSQL -> OpenWeather resolution order
- [ ] T009 Implement cache strategy: django-redis with deterministic keys and TTLs per research.md R3
- [ ] T010 Configure UTC time handling: USE_TZ=True, ISO 8601 Z serialization per research.md R9
- [ ] T011 Set up CSV export with RFC 4180 quoting and formula neutralization per research.md R7
- [ ] T012 Configure Django REST Framework pagination, filtering, and serializer validation
- [ ] T013 [US1] [P] Implement city view: two-city comparison panel with temperature, humidity, wind speed

--- PHASE 3: User Story 1 - Compare two cities side by side (P1) ---
- [ ] T013 [US1] [P] Implement city view: two-city comparison panel with temperature, humidity, wind speed
- [ ] T014 [US1] Implement per-metric difference calculation between two cities
- [ ] T015 [US1] Implement measurement time display for each city's reading
- [ ] T016 [US1] Implement same-city selection rejection with clear Spanish message: 'Las dos ciudades deben ser diferentes.'
- [ ] T017 [US1] Implement city search: accept 'City Country' and 'City, Country' forms
- [ ] T018 [US1] Implement validation: reject unknown cities with explanatory message, no placeholder values
- [ ] T019 [US1] Display instructive empty state when no city pair stored: 'Elige dos ciudades para comparar su tiempo.'
- [ ] T020 [US1] [P] Implement auto-refresh at least once per minute for selected cities
- [ ] T021 [US1] Implement manual refresh on demand for selected cities
- [ ] T022 [US1] Mark reading as stale when exceeding 60-second freshness window (badge + grayed + timestamp)
- [ ] T023 [US1] Display connection state badge: 'Live' / 'Offline' with color coding
- [ ] T024 [US1] Implement dashboard root default view: latest stored pair in URL, or empty state if fewer than two cities
- [ ] T025 [US3] [P] Implement time-series charts for both cities over selectable windows (24h, 7d, 30d)

--- PHASE 4: User Story 3 - Explore stored history (P2) ---
- [ ] T026 [US3] Implement server-side paginated table of stored observations, newest first
- [ ] T027 [US3] Implement city filter: table, pagination totals, charts, and CSV export all reflect the filter
- [ ] T028 [US3] Implement pagination controls: current page, total pages/rows, prev/next, preserve filter when pages change
- [ ] T029 [US3] Handle page beyond last: return empty result set with HTTP 200, not an error
- [ ] T030 [US3] Implement time window filter: switch between 24h, 7d, 30d, charts and table stay consistent
- [ ] T031 [US4] [P] Implement Django Channels WebSocket at /ws/weather/ with snapshot on connect

--- PHASE 5: User Story 4 - See new observations arrive without refreshing (P2) ---
- [ ] T031 [US4] [P] Implement Django Channels WebSocket at /ws/weather/ with snapshot on connect
- [ ] T032 [US4] Implement observation event on new storage, heartbeat every 25s, error codes for invalid subscriptions
- [ ] T033 [US4] Implement automatic client reconnection after disconnection without duplicating displayed records
- [ ] T034 [US4] Display connection state to user, show paused/degraded indicator when Redis unavailable
- [ ] T035 [US4] Implement reconnection recovery after Redis restart while preserving displayed data

--- PHASE 6: User Story 5 - Export filtered history to CSV (P3) ---
- [ ] T036 [US5] [P] Implement CSV export endpoint accepting Accept: text/csv
- [ ] T037 [US5] Implement RFC 4180 quoting: wrap fields in double quotes, double internal double quotes
- [ ] T038 [US5] Implement formula neutralization: prefix cells starting with =, +, -, @ with a single quote
- [ ] T039 [US5] Implement export honored active city filter and time window, independent of current page
- [ ] T040 [US5] Produce header-only file with information message when export matches no observations
- [ ] T041 [US5] Export header row: city, temperature, humidity, wind speed, measurement time, row identifier

--- FINAL PHASE: Polish & Cross-Cutting Concerns ---
- [ ] T041 [US5] Export header row: city, temperature, humidity, wind speed, measurement time, row identifier
- [ ] T042 Implement Spanish UI copy for all user-facing strings: labels, buttons, headers, states, notifications per FR-027
- [ ] T043 Implement lang='es' document declaration and API messages as technical detail within Spanish alerts per FR-027
- [ ] T044 Implement responsive layout: usable from 360-pixel-wide screens, no lost controls or overlapping content
- [ ] T045 Implement error/empty/states for all data regions: loading, empty, error, degraded (stale/offline)
- [ ] T046 Implement input validation and XSS protection: escape displayed user-supplied content, protect against injection per FR-025
- [ ] T047 Run full validation: backend pytest, ruff, mypy; frontend vitest, typecheck, lint per constitution development workflow

