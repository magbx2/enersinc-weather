# Implementation Plan: Weather Data Chat

**Branch**: `002-weather-data-chat` | **Date**: 2026-11-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-weather-data-chat/spec.md`

## Summary

Add a Spanish-language assistant panel over the already stored `WeatherData` history. The browser
never talks to an LLM provider directly: it posts a user question to Django, and the backend runs a
bounded LiteLLM tool-calling loop. Two typed, backend-owned tools (`consultar_clima` and
`calcular_estadistica`) read PostgreSQL with the ORM, validate every argument and return evidence
(city, applied filters, sample count). Arithmetic is performed only in the database; the model is
never allowed to compute or invent values. Conversations, messages and sanitized tool runs are
persisted server-side and scoped by a client-generated session id, so reloading the page restores
the identical history and run log. The model/provider is selected only through `LLM_MODEL` (and
optional `LLM_API_KEY`, `LLM_API_BASE`) configuration. The UI is an Ant Design FAB + Drawer with a
message history, a text input and a visible run status indicator; all UI-authored copy is Spanish
while artifacts and API vocabulary remain English. With no LLM credentials the product still boots;
chat reports a safe, visible `llm_not_configured` state instead of failing the stack.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.6 on Node.js 20 (frontend)

**Primary Dependencies**: existing Django 5.1 / DRF 3.15 / Channels stack plus `litellm` (provider-
agnostic SDK); React 18, Vite 5, Ant Design 5, TanStack Query 5. No new frontend dependency.

**Storage**: PostgreSQL 16 for chat sessions, messages, tool runs and weather observations; Redis
unchanged for the weather cache, Channels layer and Celery broker. Chat data is not cached.

**Testing**: pytest + pytest-django for backend unit/contract/integration tests with a fake
LiteLLM responder; Vitest + React Testing Library + MSW for the chat panel and persistence hook.

**Target Platform**: Linux containers (Docker Compose); current versions of major desktop and
mobile browsers.

**Project Type**: Web application, one served origin (Django serves the SPA and the API).

**Performance Goals**: a chat turn completes in under 10 s SC-001 for a warm model; chat history
loads in under 2 s with 100 stored messages; the panel opens without a network round trip because
the FAB and Drawer are part of the initial SPA bundle.

**Constraints**: No arbitrary SQL, shell or URLs from the model; tool arguments validated at the
boundary; never invent, interpolate or estimate weather values; LLM credentials stay server-side;
`LLM_MODEL` changes the provider without code changes; no authentication; Spanish UI copy; English
repository artifacts and API vocabulary; safe error states without secrets.

**Scale/Scope**: One operator, up to ~10 concurrent sessions, ≤100 messages loaded per session,
≤4 LLM/tool rounds per turn, tools limited to 100 rows per call, no streaming requirement.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status | Evidence |
|---|---|---|---|
| I. Microspec-First, English Artifacts, Spanish UX | Single-concern microspec exists; artifacts English; UI copy Spanish | PASS | `spec.md` is one capability (chat over stored history); this plan, research, contract and tasks are English; all FAB, Drawer, status and error copy authored by the SPA is Spanish; the assistant system prompt requires Spanish answers |
| II. Layered Data Flow, One Direction | Browser only talks to same-origin Django; credential stays server-side | PASS | SPA posts to `/chat/messages/`; Django calls LiteLLM server-side; the provider key is read from backend settings only; tools read PostgreSQL through the ORM |
| III. Cache Is a Contract | Redis keys unchanged; chat does not add undocumented cache entries | PASS | Chat reads bypass the weather cache; no new key; existing TTL table untouched |
| IV. Resilience and Truthful Data | Missing data yields an honest empty answer; no fabricated values | PASS | Tools return `no_data`/`sample_count` evidence; arithmetic is ORM `Avg/Min/Max`; the prompt forbids invention; a missing key or provider failure surfaces as a safe `llm_not_configured`/`llm_unavailable` run status |
| V. Typed Contracts and Input Validation | Inputs validated at the boundary; no SQL/shell/URL from the model | PASS | `ChatRequestSerializer`, tool argument validators, enum metrics/statistics, bounded limit and dates, JSON-only same-origin POST, sanitized persisted tool args/output; contract in `contracts/openapi.yaml` and `contracts/chat-tools.md` |
| VI. One-Command Startup | Clean checkout boots with `docker compose up`, degraded without credentials | PASS | `litellm` added to the backend image; `LLM_MODEL` has a documented default; an empty key is a supported degraded chat state; migrations run in the existing entrypoint; no new service or volume |

**Result**: No violations. Complexity tracking records the chat persistence tables and the bounded
tool loop.

**Post-design re-check (Phase 1)**: All six gates remain PASS after the data model, tool contract and
quickstart were reviewed. Chat adds no browser-to-provider path, no undocumented cache key, and no
fabrication path: every numeric answer is an ORM aggregate or a stored row.

## Project Structure

### Documentation (this feature)

```text
specs/002-weather-data-chat/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── openapi.yaml     # REST contract
│   └── chat-tools.md    # Typed tool contract
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output
```

### Source Code (repository root, changed paths)

```text
backend/
├── pyproject.toml                     # + litellm dependency
├── config/settings.py                 # + LLM_* settings and chat throttle
└── weather/
    ├── models.py                      # + ChatSession, ChatMessage, ToolRun
    ├── migrations/0002_chat.py        # new
    ├── serializers.py                 # + chat request/response serializers
    ├── errors.py                      # + chat/LLM error codes
    ├── urls.py                        # + /chat/messages/
    ├── views.py                       # + chat message/history views, health LLM status
    ├── chat/
    │   ├── __init__.py
    │   ├── agent.py                   # bounded LiteLLM tool loop
    │   ├── prompts.py                 # Spanish-answer system prompt
    │   ├── sanitize.py                # secret redaction
    │   └── tools.py                   # consultar_clima, calcular_estadistica
    └── tests/
        ├── unit/test_chat_tools.py
        ├── unit/test_chat_sanitize.py
        └── contract/test_chat.py

frontend/
└── src/
    ├── api/client.ts                  # + chat history/send
    ├── types/chat.ts                  # new
    ├── hooks/useChat.ts               # new: session id + history + mutation
    ├── components/ChatPanel.tsx       # new: FAB, Drawer, input, history, status
    ├── components/ChatPanel.test.tsx  # new
    └── pages/Dashboard.tsx            # mounts <ChatPanel />

.env.example                            # + LLM_MODEL / LLM_API_KEY / LLM_API_BASE
docker-compose.yml                      # + LLM_* backend environment
README.md                               # + chat configuration and usage
docs/architecture.md                    # + chat data flow
```

**Structure Decision**: Extend the existing `weather` Django app and the existing SPA instead of
adding a second deployable. The tools live in `weather/chat/tools.py` so they can be unit-tested
without LiteLLM, while the agent loop is isolated in `weather/chat/agent.py` and can be driven by a
fake responder in tests.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Three new persisted entities (session, message, tool run) | FR-004/FR-017 require history and tool-call logs to survive reload; server-side retention is auditable and not lost when a browser clears storage | `localStorage`-only history would not survive another browser and would expose the tool log to client tampering; an in-memory log loses audits on restart |
| Bounded multi-round tool loop (≤4) | A question may need a row query followed by a statistic; one round cannot compose evidence | A single forced tool call cannot answer "compare the average of these rows"; an unbounded loop risks runaway cost |
| Server-side LiteLLM call | FR-016/FR-018 keep credentials out of the SPA and provider changes configuration-only | A browser SDK would bundle the key and create a second provider path, violating Principle II |
