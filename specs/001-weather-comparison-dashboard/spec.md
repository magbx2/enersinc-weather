# Feature Specification: Two-City Weather Comparison Dashboard

**Feature Branch**: `001-weather-comparison-dashboard`

**Created**: 2026-11-25

**Status**: Draft

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

### Edge Cases

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

## Requirements *(mandatory)*

### Functional Requirements

**Startup and environment**

- **FR-001**: The system MUST become fully usable from a clean checkout with exactly one operator
  command and zero manual follow-up steps.
- **FR-002**: The system MUST start without any pre-existing configuration file, using safe local
  defaults, and MUST NOT require secrets to be committed.
- **FR-003**: If the external weather credential is absent or invalid, the system MUST still start and
  MUST report the live data source as unavailable.
- **FR-004**: Stored observations, cached data, and configuration MUST survive a stop-and-start cycle,
  and re-running the startup command MUST NOT require wiping stored data.
- **FR-005**: The system MUST expose whether storage, cache, and the live update channel are ready, so
  readiness can be confirmed without inspecting logs.

**City selection and comparison**

- **FR-006**: Users MUST be able to choose exactly two distinct cities and MUST be prevented from
  choosing the same city twice.
- **FR-007**: The system MUST validate each chosen city against the external source before accepting
  it, and MUST give a clear message for unknown cities.
- **FR-008**: The system MUST retrieve current temperature, humidity, and wind speed for each selected
  city and MUST persist every retrieval with the city, the three metrics, and the measurement time.
- **FR-009**: The comparison view MUST show both cities side by side, with each metric, its measurement
  time, and the numeric difference between the two cities.
- **FR-010**: The comparison view MUST indicate the age of each displayed reading and MUST mark a
  reading as stale when it exceeds the documented freshness window.
- **FR-011**: The system MUST refresh the selected cities automatically at least once per minute while a
  comparison is active, and users MUST be able to refresh on demand.

**Caching and freshness**

- **FR-012**: Recent per-city data MUST be served from cache, and the maximum cache age MUST be
  documented and MUST NOT exceed 60 seconds for current conditions.
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
  as CSV, including a header row, with correct quoting of commas, quotes, and newlines.
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
  window) and MUST reject invalid values with a clear message.
- **FR-025**: The system MUST protect against injection through user input and MUST escape displayed
  user-supplied content so that markup is shown as text rather than executed.
- **FR-026**: Every data region MUST define loading, empty, error, and degraded (stale or offline)
  states, and the layout MUST remain usable from 360-pixel-wide screens upward.

### Key Entities

- **Weather Observation**: A single recorded reading for one city, with city name, temperature,
  humidity, wind speed, and the time the reading was measured. This is the only source of displayed
  values.
- **City**: A place the user can compare, identified by a name and a stable external identifier used
  to disambiguate cities with the same name.
- **Comparison Selection**: The pair of currently selected cities, their latest readings, and the
  derived per-metric differences and freshness status.
- **Data Freshness Status**: Whether a reading is current, stale, or unavailable, derived from its
  measurement time and the documented freshness window.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a clean machine with no prior configuration, one command brings the whole product to a
  usable state in under 5 minutes, with zero manual steps, in 100% of attempts.
- **SC-002**: A user completes a first two-city comparison in under 30 seconds without reading
  instructions.
- **SC-003**: For cities already cached, the comparison is visible within 2 seconds for at least 95% of
  page loads.
- **SC-004**: At least 95% of new observations appear on every open dashboard within 5 seconds, without
  user action.
- **SC-005**: During an external source outage, 100% of dashboard loads still show the last known
  readings marked as not current; no dashboard shows blank or fabricated values.
- **SC-006**: In an audit of displayed values, 100% trace to a stored observation.
- **SC-007**: Exporting up to 10,000 matching observations completes within 10 seconds and matches the
  filtered on-screen set in 100% of tested cases.
- **SC-008**: After a stop-and-start cycle, 100% of previously stored observations remain available.
- **SC-009**: All dashboard areas remain operable at a 360-pixel viewport width with no lost or
  overlapping controls.

## Assumptions

- The primary user is a single evaluator or analyst with no account, role, or authentication; the
  product is local and single-tenant.
- Cities are chosen by free-text name and validated against the external weather source; a fixed
  curated list is not required.
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
