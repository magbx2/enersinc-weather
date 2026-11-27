# Phase 0 Research: Weather Data Chat

**Feature**: 002-weather-data-chat | **Date**: 2026-11-26

## R1. Provider-agnostic LLM access

**Decision**: Use the LiteLLM Python SDK (`litellm.completion`) server-side, with the model name
read from `LLM_MODEL`.

**Rationale**: LiteLLM accepts `provider/model` strings and normalizes the OpenAI-style chat and
tool-calling interface across providers. Changing from `openai/gpt-4o-mini` to
`anthropic/claude-3-5-sonnet` is an environment change only, satisfying FR-018 and SC-008.

**Alternatives considered**:
- Direct OpenAI SDK: fast, but reintroduces vendor lock-in and requires code changes per provider.
- LiteLLM proxy container: adds a service and a second network hop; the SDK already provides the
  required abstraction for a single-process Django deployment.
- Local model only: not portable and not required by the spec.

**Configuration**:

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `LLM_MODEL` | no | `gpt-4o-mini` | LiteLLM model identifier; changing it changes provider/model |
| `LLM_API_KEY` | no | empty | Explicit key; when empty the provider SDK's own environment variables are used |
| `LLM_API_BASE` | no | empty | Optional compatible proxy/gateway URL |
| `LLM_TIMEOUT_SECONDS` | no | `30` | Hard upper bound per model call |
| `LLM_MAX_TOOL_ROUNDS` | no | `4` | Bound for the tool-calling loop |

When no usable key is present the backend answers with the safe `llm_not_configured` error code and
the UI shows a Spanish explanation. Startup never fails because of missing LLM credentials.

## R2. Conversation persistence and session identity

**Decision**: Generate a UUID v4 in the browser and store it in `localStorage` under
`weather-chat-session`. Every request sends it; Django `get_or_create`s a `ChatSession`. Messages
and tool runs are stored in PostgreSQL and returned by `GET /chat/messages/?session_id=...`.

**Rationale**: FR-004/FR-017 require history and tool logs to survive reloads and to be auditable.
Server-side rows are stable across tabs and browsers that know the session id, and they let the
backend keep sanitized (not client-supplied) tool records. The session id is not an authentication
token: there is no authentication in scope and the data is non-sensitive weather history.

**Alternatives considered**:
- `localStorage` for the full transcript: simplest, but the tool log becomes client-controlled and
  the history cannot be inspected server-side. Rejected.
- Cookie-based session: works, but requires CSRF/cookie handling for a JSON API that currently uses
  an explicit same-origin marker. A UUID in the body/query is simpler and consistent.

## R3. Typed tools and abstention

**Decision**: Two tools with fixed JSON schemas:

1. `consultar_clima(city, start?, end?, limit?)` — stored rows for one city in `[start, end)`,
   newest first, `limit` 1–100 (default 20).
2. `calcular_estadistica(city, metric, statistic, start?, end?)` — ORM `Avg`/`Min`/`Max` over the
   same filter; `metric` ∈ `temperature|humidity|wind_speed`, `statistic` ∈ `average|minimum|maximum`.

**Rationale**: FR-008..FR-012. Dates accept ISO 8601 date-times with an offset or plain dates
(`YYYY-MM-DD`), converted to UTC. `city` is mandatory for both tools. Missing or malformed
arguments return a tool error the model must turn into a clarification question; it never receives
fabricated defaults. Missing rows return `no_data: true` with `sample_count: 0`, not an error.

**Alternatives considered**:
- Free-form SQL tool: impossible to validate and explicitly forbidden by FR-012.
- A single mega-tool with an action switch: less discoverable for the model and harder to type.
- Letting the model compute statistics: violates FR-009/SC-004.

## R4. Evidence, sanitization and safe errors

**Decision**: Every tool result carries `evidence`: matched city and `city_key`, the effective
`start`/`end`, `sample_count`, and for row queries the returned rows and total matched. Tool
arguments and outputs are persisted after recursive redaction of keys matching
`api_key|token|secret|password|authorization` and of string values that look like provider keys.
LLM/tool failures are stored with an English error code and no provider body.

**Rationale**: FR-011, FR-015, SC-010. Sanitization runs before persistence and before the API
response, so a future tool that receives a credential-like argument cannot leak it through the
history.

## R5. Status semantics

**Decision**: Each assistant message has `status` ∈ `completed|failed` and an optional
`error_code`. During processing the SPA renders a local `in_progress` indicator; after the
response it renders `completed` with the tool tags, or `failed` with Spanish copy and the code as
technical detail.

**Rationale**: FR-003, FR-005, SC-007. No streaming is required, so a synchronous request plus a
local pending state is sufficient and keeps the contract simple.

## R6. Validation limits

- User message: 1–2000 characters, not blank.
- Session id: UUID v4 string.
- Tool city: existing `normalize_city` (length, control characters, markup, allowed characters).
- Row limit: 1–100.
- Date range: `start < end`; both optional; defaults to the last 30 days for statistics and rows.
- History: latest 100 messages, oldest-first in the response.
- Same-origin JSON POST reuses `_enforce_same_origin` from the dashboard.

## R7. Testing strategy

- Unit: tool validation, range parsing, aggregation correctness against known rows, sanitizer.
- Contract: `POST /chat/messages/` with a fake LiteLLM responder that requests a tool then answers;
  persistence across requests; history ordering; invalid payloads; LLM failure mapping.
- Integration: full loop against seeded `WeatherData` verifying the assistant's evidence and
  database-computed statistic.
- Frontend: FAB opens the Drawer, history loads from the stored session, send shows the pending
  indicator, tool tags render, failure shows Spanish copy, reload keeps the session id.
