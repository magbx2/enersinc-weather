# Feature Specification: Weather Data Chat

**Feature Branch**: `002-weather-data-chat`

**Created**: 2026-11-26

**Status**: Proposed

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Natural language queries over stored weather history (Priority: P1)

A technical assistant asks natural-language questions about the stored historical weather data and receives accurate answers grounded in the real data, with no fabrications.

**Why this priority**: The product already holds a persisted WeatherData history. Building a chat over this data adds immediate value by letting users explore and extract information from the historical data through natural language, instead of requiring SQL queries or manual filtering.

**Independent Test**: A user opens the chat panel, enters a natural-language question about historical weather (for example, "¿Cuál fue la temperatura promedio en Buenos Aires en agosto?" or "¿Cuál fue la máxima en Madrid durante el último mes?"), and the system answers with accurate data from the database, showing the city, the date range and the computed statistic. If there is no data for the query, the system says so clearly instead of inventing an answer.

**Acceptance Scenarios**:

1. **Given** the chat is open and the user enters "¿Cuál fue la temperatura promedio en Buenos Aires?", **When** the system processes the question, **Then** it returns the average temperature along with the date range considered and evidence of how many records were used. If there is no data, it shows an instructive message.

2. **Given** the user filters by city and date range, **When** the system queries, **Then** it returns only the records matching the city and date criteria, in the specified format (rows or aggregate).

3. **Given** the user requests a statistic (average, minimum, maximum) of the temperature, **When** the system computes it, **Then** it uses backend arithmetic, never the LLM, and returns the result with the city, metric and date range applied.

4. **Given** the user asks a question without specifying a city or dates, **When** the system validates the parameters, **Then** it asks the user for clarification instead of inventing values or applying default filters.

5. **Given** the chat has conversation history, **When** the user reloads the page, **Then** the message history persists and remains available.

---

### User Story 2 - Configurable LLM without vendor lock-in (Priority: P2)

The language model can be changed through configuration only (the `LLM_MODEL` environment variable), without modifying the code.

**Why this priority**: It guarantees that the LLM provider can be swapped (for example, from OpenAI to Anthropic or another) by changing configuration only, avoiding lock-in to a specific provider.

**Independent Test**: The application starts with an `LLM_MODEL` variable configured. The variable is changed to another compatible provider and the application works with no code changes, using the new model for the chat responses.

**Acceptance Scenarios**:

1. **Given** the `LLM_MODEL` environment variable is set to a valid provider, **When** the chat generates a response, **Then** it uses that model/provider according to the configuration.

2. **Given** `LLM_MODEL` is changed to a different provider, **When** the chat generates a response, **Then** it uses the new provider without requiring code restructuring.

3. **Given** `LLM_MODEL` is not configured, **When** the chat attempts to generate a response, **Then** it uses a documented default model and shows a status indicator.

---

### User Story 3 - Persistence and run logging (Priority: P2)

Conversations and tool calls are logged briefly, and the history survives a page reload.

**Why this priority**: Users must be able to trust that their question history is available and to review which tools were called and with which arguments, for debugging and auditing purposes.

**Independent Test**: A user sends several questions in the chat, reviews the tool-call history, reloads the page and confirms that both the messages and the tool-call log are still present and unchanged.

**Acceptance Scenarios**:

1. **Given** the user has asked questions and the system has called tools, **When** the user reloads the page, **Then** the message history and the tool-call log (name, args, sanitized output) persist exactly as they were displayed.

2. **Given** a tool is called, **When** the tool returns a result, **Then** the log includes the tool name, the validated arguments and the output with secrets removed.

---

### User Story 4 - Accessible frontend with FAB + input + history (Priority: P3)

The chat panel has an interface composed of a FAB, a text input and a message history, with a run status indicator.

**Why this priority**: It provides an intuitive and consistent user interface that integrates with the rest of the product.

**Independent Test**: The chat panel loads and it is confirmed that: (a) there is a FAB button to open the chat, (b) there is an input field at the bottom, (c) the message history is shown above, (d) there is a visible status indicator during processing.

**Acceptance Scenarios**:

1. **Given** the chat panel is closed, **When** the user clicks the FAB, **Then** the panel opens showing the history and the text input.

2. **Given** a question is being processed, **When** the system responds, **Then** the status indicator shows the result and which tools were called (without secrets).

3. **Given** the viewport is narrow, **When** the panel is used, **Then** all controls remain operable without being lost or overlapping.

---

## Requirements *(mandatory)*

### Functional Requirements

**Chat and interface**

- **FR-001**: Users must be able to ask natural-language questions and receive answers grounded in the stored WeatherData history, with no fabrications or hallucinations.

- **FR-002**: The system must provide a chat panel with a FAB (Floating Action Button), an input field and a message history.

- **FR-003**: There must be a visible status indicator showing whether a run is in progress, completed or failed.

- **FR-004**: The message history and the tool-call log must survive page reloads.

- **FR-005**: The frontend must show a brief view of which tools were called (name, no secrets) for each user response.

- **FR-006**: The LLM model must be configurable through an environment variable only (`LLM_MODEL` in `.env`), with no code changes.

- **FR-007**: `.env` and `.env.example` must have a documented format, but real values must be absent from `.env.example`.

**Typed tools**

- **FR-008**: A `consultar_clima` tool must exist that filters by city and/or date range and returns rows or aggregates from the database, without inventing data.

- **FR-009**: A `calcular_estadistica` tool must exist that computes the average/minimum/maximum of the temperature (or another metric) over a subset, with backend arithmetic, not in the LLM.

- **FR-010**: Both tools must validate their arguments and abstain when mandatory parameters are missing, asking for clarification instead of inventing.

- **FR-011**: The tools must return evidence (city, filters applied, IDs or counts used) for every call.

- **FR-012**: Arbitrary SQL, free shell or free URLs are not allowed in the tools. Arguments must be validated.

**Agent behavior**

- **FR-013**: The agent must choose tools and return evidence (city, filters, IDs or counts used).

- **FR-014**: If there is no data or a parameter is missing, the agent must ask for clarification instead of inventing.

- **FR-015**: Tool or LLM errors must be handled visibly and safely (without leaking secrets).

- **FR-016**: The LLM credentials must live only in the backend; `.env.example` must not contain real values.

**Chat persistence**

- **FR-017**: The system must persist conversations/messages and, where possible, a brief log of runs or tool calls (name, args, sanitized output). The history must survive reloads.

**LLM**

- **FR-018**: It must be built with LiteLLM (SDK or proxy) so that the model/provider can be changed through configuration only (for example, the `LLM_MODEL` variable in `.env`), without vendor lock-in or code changes.

- **FR-019**: The model used and how to change it must be documented.

---

### Key Entities

- **Chat message**: A unit of conversation containing the text of the user's question, the generated answer, the list of tools called (name, sanitized args, output) and the timestamp.

- **Tool run**: A call executed in the backend with a tool name (`consultar_clima` or `calcular_estadistica`), the validated arguments and the resulting output (with sensitive data removed).

- **City filter**: The city name by which queries are filtered (e.g., "Buenos Aires", "Madrid").

- **Date range**: The period by which the data is filtered (e.g., "last month", "August 2024", "last 30 days").

- **Statistics**: Computed metrics (average, minimum, maximum) of the temperature or another metric available in the WeatherData.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can ask a natural-language question about historical data and receive an answer grounded in real data in under 10 seconds, measured from submitting the question to displaying the answer.

- **SC-002**: The chat panel loads and is operable in under 2 seconds after clicking the FAB, measured with a probe of 20 requests and recorded in `docs/performance.md`.

- **SC-003**: When filtering by city and date range, the system returns exactly the matching records (100% match in test cases with known data), with no extra records and no silent losses.

- **SC-004**: When a statistic (average/minimum/maximum) is requested, the result is mathematically correct when compared against the raw database data, with a maximum deviation of 0.01°C.

- **SC-005**: If the user asks a question without specifying a city or dates, the system asks for clarification instead of inventing values (100% of cases in testing).

- **SC-006**: The message history and tool calls survive a page reload (100% retention in reload testing).

- **SC-007**: The run status indicator is accurate (it shows "en progreso", "completado" or "fallado" correctly) in at least 95% of cases across scenario testing.

- **SC-008**: The `LLM_MODEL` variable can be changed to a different provider and the chat keeps working with no code changes (demonstrated by switching providers and confirming responses).

- **SC-009**: `.env.example` contains no real values (verified that there are no API keys or secrets in the file).

- **SC-010**: The tools return evidence of city, filters applied and counts in at least 98% of calls, in a consistent format.

---

## Assumptions

- The WeatherData history is already persisted in the PostgreSQL database with the structure defined in the WeatherData model (city, temperature, humidity, wind_speed, timestamp).

- Users are technical staff or analysts who can ask questions about the historical weather data; there is no authentication or multiple roles in this microspec.

- Natural-language questions map to city and date-range filters and/or statistic requests (average/minimum/maximum). The system does not attempt complex full-intent parsing; it extracts the key parameters for the tools.

- LiteLLM is available and configured as a proxy or SDK to support multiple LLM providers through a single API.

- Chat persistence uses client-side storage (localStorage or similar) or a server-side session with a session ID, so that the history survives reloads.

- The `consultar_clima` and `calcular_estadistica` tools are implemented as API endpoints in the Django backend, with argument validation.

- The units are metric: Celsius for temperature and meters per second for `wind_speed`.

- Common date ranges include: "last 24 h", "last 7 d", "last 30 d", specific months or absolute dates.

---

## Notes

- This microspec is independent of the 001-weather-comparison-dashboard spec but shares the same database and backend.

- The agent must abstain when there is no data or a parameter is missing; it must ask for clarification instead of inventing.

- Tool or LLM errors must be visible and safe (without leaked secrets).

- The LLM credentials must live only in the backend; `.env.example` without real values.

- The LLM model must be configurable through an environment variable without code changes.

- The chat history must survive a page reload.

- Frontend: FAB + input + history; run status indicator; brief view of which tools were called (without secrets). Streaming is not mandatory.
