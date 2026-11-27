# Feature Specification: Two-City Weather Comparison Dashboard

**Feature Branch**: `001-weather-comparison-dashboard`

**Created**: 2026-11-25

**Status**: Implemented

**Input**: User description: "Build a dashboard that compares the weather of two cities, with real-time
updates, persisted history, mandatory caching, CSV export, and a frontend served as the root route.
Everything must work by running only the single local startup command."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Compare two cities side by side (Priority: P1)

A visitor opens the dashboard, chooses two different cities, and immediately sees their current
weather side by side: temperature, humidity, and wind speed, each with the time it was measured,
plus the difference between the cities for every metric.

**Why this priority**: This is the product's reason to exist. Without a working two-city
comparison, no other capability delivers value.

**Independent Test**: Open the dashboard, select two distinct cities, and confirm both panels show
current values, measurement times, and per-metric differences, with no page reload required.

**Acceptance Scenarios**:

1. **Given** the dashboard is open and no city is selected, **When** the visitor selects two distinct
   cities, **Then** both panels show temperature, humidity, wind speed, the measurement time, and
   the numeric difference for each metric.
2. **Given** one city is already selected, **When** the visitor selects the same city for the second
   slot, **Then** the selection is rejected with a clear message and the previous valid selection
   remains intact.
3. **Given** the visitor enters a city the weather provider does not recognize, **When** the
   selection is submitted, **Then** an explanatory message is shown and no empty or placeholder
   values are displayed as if they were real.
4. **Given** a city has never been observed before, **When** it is selected, **Then** the system
   fetches its current conditions, stores the observation, and displays it.
5. **Given** the visitor opens the dashboard root without a city pair, **When** the page loads,
   **Then** the two cities with the most recent stored observations are shown and reflected in the
   URL; if fewer than two stored cities exist, an instructive empty state is shown instead.

---

### User Story 2 - Start the whole system with a single command (Priority: P1)

An evaluator takes a clean checkout on a machine with only the container runtime installed, runs
exactly one command, and the whole product becomes usable: storage, cache, live updates, and the
web interface. No migration, seeding, configuration file, build step, or service-by-service startup
is performed by hand.

**Why this priority**: It is the release gate for the entire deliverable. Any capability that
requires undocumented manual steps cannot be demonstrated, tested, or handed over.

**Independent Test**: On a clean checkout with no prior configuration and no running services, run
the single documented startup command, then load the dashboard and complete one comparison without
any further action.

**Acceptance Scenarios**:

1. **Given** a clean checkout and no configuration file, **When** the single startup command is run,
   **Then** the dashboard becomes reachable in a browser and reports its dependencies as ready.
2. **Given** the system was stopped, **When** it is started again, **Then** all previously stored
   observations are still present and the dashboard works without repeating setup.
3. **Given** no external weather credential is configured, **When** the system starts, **Then** it
   starts successfully and reports the live data source as unavailable instead of failing to boot.
4. **Given** the system is already running, **When** the same startup command is issued again,
   **Then** it completes without deleting stored data or requiring manual cleanup.

---

### User Story 3 - Explore the stored history of both cities (Priority: P2)

A visitor reviews how the two cities evolved: time-series charts for both cities over a selectable
window, and a table of stored observations with a city filter and page-by-page navigation, newest
first.

**Why this priority**: The comparison is more useful when it is not limited to the current moment;
history turns the dashboard into an analysis tool.

**Independent Test**: With observations already stored for two cities, open the history area, switch
the time window, filter the table by one city, and page through results while confirming the charts
and table stay consistent with the stored data.

**Acceptance Scenarios**:

1. **Given** stored observations exist for both cities, **When** the visitor opens the charts,
   **Then** both series are plotted on a shared time axis for the selected window (24 hours, 7 days,
   or 30 days).
2. **Given** the table shows the newest observations first, **When** the visitor moves to the next
   page, **Then** a different, non-overlapping set of observations is shown and the current page and
   total count are visible.
3. **Given** the visitor filters by one city, **When** the filter is applied, **Then** the table, its
   pagination totals, the charts, and the CSV export all reflect that filter.
4. **Given** the visitor requests a page beyond the last available page, **When** the results load,
   **Then** an empty-state message is shown and no error is raised.

---

### User Story 4 - See new observations arrive without refreshing (Priority: P2)

While the dashboard is open, newly recorded observations for the selected cities appear
automatically, with a visible indicator that live updates are connected.

**Why this priority**: "Real time" is a core product promise and the main differentiator against a
static weather page.

**Independent Test**: Keep the dashboard open while a new observation is recorded for one selected
city and confirm the affected panels, chart, and table update within seconds without user action.

**Acceptance Scenarios**:

1. **Given** the dashboard is open with two cities selected, **When** a new observation is stored for
   one of them, **Then** the affected values, chart point, and table row update automatically without
   a page reload.
2. **Given** the live connection drops, **When** connectivity returns, **Then** the client reconnects
   automatically, shows the connection state, and resumes receiving updates without duplicating
   previously displayed records.
3. **Given** live updates are unavailable, **When** the visitor loads the dashboard, **Then** it still
   works using the latest stored data and clearly indicates that values are not live.

---

### User Story 5 - Export the filtered history to CSV (Priority: P3)

A visitor downloads the observations currently in view as a spreadsheet-friendly file.

**Why this priority**: Useful for reporting and offline analysis, but the product is already valuable
without it.

**Independent Test**: Apply a city filter and a time window, trigger the export, and open the file in a
spreadsheet tool to confirm the rows and columns match the on-screen selection.

**Acceptance Scenarios**:

1. **Given** a city filter and window are applied, **When** the visitor exports, **Then** the file
   contains exactly the observations matching that filter and window, with a header row.
2. **Given** a city name or value contains a comma, quote, or newline, **When** the file is exported,
   **Then** the affected fields are quoted correctly and the file opens without breaking columns.
3. **Given** no observations match the current filter, **When** the visitor exports, **Then** a file
   with only the header row is produced and the visitor is told the export was empty.

---

## Clarifications

**Session 2026-11-26**

- Q: How should the dashboard visually indicate that a reading is stale (exceeds the 60-second freshness window)?
  A: All of the above - combining "Stale" text badge, grayed-out appearance with age tooltip, and "Last updated: [time]" timestamp display provides the clearest communication of freshness status.
- Q: How should the CSV export handle city names or values that contain commas, quotes, or newlines?
  A: RFC 4180 standard quoting: wrap fields in double quotes and double any internal double quotes. This is the most interoperable approach and aligns with the project constitution's RFC 4180 quoting requirement (Principle V).
- Q: How should the dashboard display the live connection state to the user?
  A: "Live" / "Offline" badge with color coding (green/orange-red) providing immediate status awareness, complying with Spanish UI requirements (FR-027).
- Q: What content should the dashboard show in the empty state when no city pair has been stored yet?
  A: "No ciudades seleccionadas aún. Buscar una ciudad para comenzar." - concise, action-oriented, compliant with Spanish UI requirements (FR-027).
- Q: What columns should the CSV export header row contain, and in what order?
  A: `city, temperature, humidity, wind speed, measurement time, row identifier` - follows entity definition order includes stable row reference for diagnostics.

## Edge Cases

- The external weather source is slow, unavailable, rate-limited, or rejects the credential: the
  dashboard MUST keep working with the most recent stored data and MUST label it as not current.
- Two identical cities are selected: the system MUST reject the selection with a clear message.
- A city name is empty, excessively long, contains markup, or contains characters intended to break
  a query: the system MUST reject it with a clear validation message and MUST NOT echo it unsafely.
- No observations exist at all (first run): the dashboard MUST show an instructive empty state, not
  blank panels or fabricated zeroes.
- A selected city has current conditions available but no history yet: the current comparison MUST
  render and the history area MUST explain that no history is stored yet.
- Only one of the two cities has data: the dashboard MUST show the available side and mark the other
  as unavailable rather than imitating a value.
- The cache layer is unavailable while storage is healthy: requests MUST still succeed by reading
  stored data, without user-visible failure.
- The live connection is lost and restored repeatedly: updates MUST resume without duplicated rows.
- The system is restarted while the browser page is open: stored data MUST remain and the page MUST
  recover its live connection.
- Very large histories or very wide date ranges are requested: the interface MUST remain responsive
  and MUST bound the amount of data returned per request.
- The browser is narrow (down to 360 pixels wide): all dashboard areas MUST remain usable without
  losing controls or overlapping content.
- The dashboard root is opened with no pair and no stored observations: the system MUST show an
  instructive empty state and MUST NOT call the provider until the visitor asks for a refresh.
- The provider is unavailable but stored observations exist for a searched city: search MUST return
  those stored cities so the visitor can still build a comparison from history.
- Two cities share a name but belong to different countries: the name-based identity is documented
  as a limitation, and the interface MUST show the stored country code for each reading instead of
  implying that both rows belong to the same known country.
- A visitor requests a page beyond the last page: the system MUST return an empty result set with
  HTTP 200, not an error.
- **Readings exceeding the 60-second freshness window MUST be indicated using all of the following complementary visual cues: a "Stale" text badge over the value, a grayed-out appearance, and a "Last updated: [time]" timestamp display.**
- Two identical cities are selected: the system MUST reject the selection with a clear message.
- A city name is empty, excessively long, contains markup, or contains characters intended to break
  a query: the system MUST reject it with a clear validation message and MUST NOT echo it unsafely.
- No observations exist at all (first run): the dashboard MUST show an instructive empty state, not
  blank panels or fabricated zeroes.
- A selected city has current conditions available but no history yet: the current comparison MUST
  render and the history area MUST explain that no history is stored yet.
- Only one of the two cities has data: the dashboard MUST show the available side and mark the other
  as unavailable rather than imitating a value.
- The cache layer is unavailable while storage is healthy: requests MUST still succeed by reading
  stored data, without user-visible failure.
- The live connection is lost and restored repeatedly: updates MUST resume without duplicated rows.
- The system is restarted while the browser page is open: stored data MUST remain and the page MUST
  recover its live connection.
- Very large histories or very wide date ranges are requested: the interface MUST remain responsive
  and MUST bound the amount of data returned per request.
- The browser is narrow (down to 360 pixels wide): all dashboard areas MUST remain usable without
  losing controls or overlapping content.
- The dashboard root is opened with no pair and no stored observations: the system MUST show an
  instructive empty state and MUST NOT call the provider until the visitor asks for a refresh.
- The provider is unavailable but stored observations exist for a searched city: search MUST return
  those stored cities so the visitor can still build a comparison from history.
- Two cities share a name but belong to different countries: the name-based identity is documented
  as a limitation, and the interface MUST show the stored country code for each reading instead of
  implying that both rows belong to the same known country.
- A visitor requests a page beyond the last page: the system MUST return an empty result set with
  HTTP 200, not an error.

## Requirements *(mandatory)*

### Functional Requirements

**Startup and environment**

- **FR-001**: The system MUST become fully usable from a clean checkout with exactly one operator
  command and zero manual follow-up steps.
- **FR-002**: The system MUST start without any pre-existing configuration file, using safe local
  defaults, and MUST NOT require secrets to be committed.
- **FR-003**: If the external weather credential is absent, the system MUST still start and health MUST
  report `provider_configured: false`. If the credential is present but rejected, the first provider
  request MUST surface `credential_invalid` and the dashboard MUST show stored readings marked
  stale with that reason.
- **FR-004**: Stored observations, cached data, and configuration MUST survive a stop-and-start cycle,
  and re-running the startup command MUST NOT require wiping stored data.
- **FR-005**: The system MUST expose whether storage, cache, provider configuration and the
  scheduler are ready, so readiness can be confirmed without inspecting logs. Live-update readiness
  is inferred from the Redis-backed cache and group layer, which both use the same connection.

**City selection and comparison**

- **FR-006**: Users MUST be able to choose exactly two distinct cities and MUST be prevented from
  choosing the same city twice.
- **FR-007**: The system MUST validate each chosen city before fetching its current conditions and
  MUST give a clear message for unknown cities. City search MUST resolve in this order:
  Redis geocoding cache, then PostgreSQL observations already stored, then the external provider.
  Search input MUST accept both `City Country` and `City, Country` forms; an unconfigured provider
  MUST still return cities that already have stored observations.
- **FR-008**: The system MUST retrieve current temperature, humidity, and wind speed for each selected
  city and MUST persist every retrieval with the city, the three metrics, and the measurement time.
- **FR-009**: The comparison view MUST show both cities side by side, with each metric, its measurement
  time, and the numeric difference between the two cities.
- **FR-010**: The comparison view MUST indicate the age of each displayed reading and MUST mark a
  reading as stale when it exceeds the documented freshness window.
- **FR-011**: The system MUST refresh the selected cities automatically at least once per minute while a
  comparison is active, and users MUST be able to refresh on demand. Scheduled background refresh
  MUST cover at most the 10 cities observed in the last 24 hours so history keeps accumulating
  without an open browser.

**Caching and freshness**

- **FR-012**: Recent per-city data MUST be served from a cache-aside `weather:current` entry, and the
  maximum cache age MUST be documented and MUST NOT exceed 60 seconds for current conditions.
- **FR-013**: A cache miss or cache outage MUST be served transparently from stored history, without
  failing the request.
- **FR-014**: When a new observation is stored, any cached entry for that city MUST be replaced or
  invalidated immediately so the next read is not older than the new observation.

**History, table, and export**

- **FR-015**: The system MUST provide time-series charts comparing both cities over selectable windows
  of 24 hours, 7 days, and 30 days.
- **FR-016**: The system MUST provide a table of stored observations, newest first, paginated on the
  server with a configurable page size and a city filter.
- **FR-017**: The table MUST display the current page, total pages or total rows, and working previous
  and next controls, and MUST keep the filter when pages change.
- **FR-018**: Users MUST be able to export the observations matching the active city filter and window
  as CSV, including a header row, with correct quoting of commas, quotes, and newlines. The export
  endpoint MUST accept `Accept: text/csv` even though the project's default renderer is JSON.
- **FR-019**: When an export matches no observations, the system MUST produce a header-only file and
  inform the user that the export was empty.

**Real-time updates**

- **FR-020**: When a new observation is stored, the system MUST notify connected dashboards, and those
  dashboards MUST update the affected comparison values, chart, and table without a page reload.
- **FR-021**: The dashboard MUST display the state of the live connection and MUST reconnect
  automatically after a disconnection without duplicating displayed observations.

**Resilience, truthfulness, and input safety**

- **FR-022**: When the external source fails, the system MUST fall back to the most recent stored
  observation, mark it as not current, and record a diagnostic log entry that distinguishes an
  external-source failure from a storage or cache failure.
- **FR-023**: The system MUST NOT invent, interpolate, or estimate any displayed value; every number
  shown MUST be traceable to a stored observation.
- **FR-024**: The system MUST validate every user-supplied value (city, page number, page size, time
  window) and MUST reject invalid values with a clear message. A page number below 1 is invalid; a
  page beyond the last page is valid and MUST return an empty result set with HTTP 200.
- **FR-025**: The system MUST protect against injection through user input and MUST escape displayed
  user-supplied content so that markup is shown as text rather than executed.
- **FR-026**: Every data region MUST define loading, empty, error, and degraded (stale or offline)
  states, and the layout MUST remain usable from 360-pixel-wide screens upward.

**Presentation and default view**

- **FR-027**: All UI-authored user-facing copy MUST be Spanish, including labels, buttons, table
  headers, chart titles, notifications, validation messages authored by the interface,
  empty/loading/error/degraded states, accessibility labels and live-region announcements. Every
  alert MUST contain Spanish UI-authored copy; English API messages MAY appear as technical detail
  within the alert. The document MUST declare `lang="es"`. Repository artifacts, code identifiers,
  tests, contracts and developer documentation MUST remain English.
- **FR-028**: Opening the dashboard root without a city pair MUST show the two cities with the most
  recent stored observations and reflect that pair in the URL. When fewer than two stored cities
  exist, the dashboard MUST show an instructive empty state and MUST NOT call the provider unless a
  refresh is explicitly requested.

### Key Entities

- **Weather Observation**: A single recorded reading for one city, with city name, temperature,
  humidity, wind speed, and the time the reading was measured. This is the only source of displayed
  values. An internal row identifier is used for diagnostics and is included in the CSV export as a
  stable row reference.
- **City**: A place the user can compare, identified by its display name and optional ISO country
  code. The normalized name forms `city_key`, which is the persisted identity used by filters,
  cache keys and channel groups. The provider's numeric city identifier is available in search
  candidates but is not persisted; same-name cities in different countries therefore share a
  `city_key` in this delivery.
- **Comparison Selection**: The pair of currently selected cities, their latest readings, and the
  derived per-metric differences and freshness status.
- **Data Freshness Status**: Whether a reading is current, stale, or unavailable, derived from its
  measurement time and the documented freshness window.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a clean machine with no prior configuration, one command brings the whole product to a
  usable state in under 5 minutes, measured and recorded by the quickstart V2 scenario.
- **SC-002**: A first two-city comparison is reachable in at most three interactions from `/` (open the
  root, select the first city, select the second city) without consulting documentation.
- **SC-003**: At least 95% of dashboard requests (p95) complete within 2 seconds when the city pair is
  cached, measured by the documented 20-request probe and recorded in `docs/performance.md`.
- **SC-004**: At least 95% of new observations appear on every open dashboard within 5 seconds, without
  user action; the V4 manual check and the timestamped fan-out tests are the evidence.
- **SC-005**: During an external source outage, 100% of dashboard loads still show the last known
  readings marked as not current; no dashboard shows blank or fabricated values.
- **SC-006**: In an audit of displayed values, 100% trace to a stored observation; the audit procedure
  is recorded as quickstart scenario V8.
- **SC-007**: Exporting up to 10,000 matching observations completes within 10 seconds and matches the
  filtered on-screen set in 100% of tested cases.
- **SC-008**: After a stop-and-start cycle, 100% of previously stored observations remain available.
- **SC-009**: All dashboard areas remain operable at a 360-pixel viewport width with no lost or
  overlapping controls.

## Assumptions

- The primary user is a single evaluator or analyst with no account, role, or authentication; the
  product is local and single-tenant.
- All repository artifacts, code identifiers, tests, contracts and developer documentation are
  English. All UI-authored user-facing copy is Spanish, the document declares `lang="es"`, and
  English API messages appear only as technical detail within Spanish alerts.
- Cities are chosen by free-text name and validated against the external weather source; a fixed
  curated list is not required. Search resolves through Redis, then PostgreSQL, then the provider.
- The persisted city identity is the normalized name (`city_key`) plus an optional country code.
  The provider's numeric identifier is search-only and is not stored, so same-name cities in
  different countries are not disambiguated in this delivery.
- Opening `/` without a city pair shows the latest stored pair; the provider is only contacted when
  a refresh is explicitly requested.
- A live refresh resolves city coordinates through the provider; stored observations support search
  and history but are not enough to fetch a new reading.
- Units are metric: temperature in degrees Celsius, wind speed in meters per second. Unit switching
  is out of scope.
- The documented freshness window for current conditions is 60 seconds, aligned with the automatic
  refresh interval.
- The history windows offered are exactly 24 hours, 7 days, and 30 days.
- CSV export covers all observations matching the active filter and window, not only the current page.
- Observations are retained indefinitely; no retention limit or purge policy is required for this
  delivery.
- The project constitution fixes the delivery stack and mandates that the single startup command is
  `docker compose up`; this specification deliberately describes behavior, not implementation.
- The agent-based chat over stored history is a separate microspec and is out of scope here.
- Authentication, multi-user collaboration, alerting or notifications, native mobile applications,
  and third-party weather widgets are out of scope.
- The machine running the product has a container runtime and sufficient memory for the declared
  services; browser support targets current versions of major desktop and mobile browsers.