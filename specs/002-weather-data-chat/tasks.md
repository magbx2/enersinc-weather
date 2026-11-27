# Tasks: Weather Data Chat

**Generated from** [spec.md](./spec.md), [plan.md](./plan.md), [data-model.md](./data-model.md) and
[contracts/](./contracts/).

## Task Organization

- Setup (Phase 1), Foundational (Phase 2), User stories by priority (Phase 3+), Polish (final).
- Every task follows `- [ ] T### [P?] [USx?] Description with file path`.
- `[P]` = safe to run in parallel with other `[P]` tasks in the same phase.

--- PHASE 1: Setup ---
- [x] T001 Add `litellm` to `backend/pyproject.toml` and rebuild the backend image
- [x] T002 Add `LLM_MODEL`, `LLM_API_KEY`, `LLM_API_BASE`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_TOOL_ROUNDS` to `backend/config/settings.py`
- [x] T003 Add the `chat` throttle scope to `REST_FRAMEWORK` in `backend/config/settings.py`
- [x] T004 Add `LLM_*` variables to `.env.example` and pass them through `docker-compose.yml`
- [x] T005 [P] Document model configuration and usage in `README.md`

--- PHASE 2: Foundational ---
- [x] T006 Create `ChatSession`, `ChatMessage` and `ToolRun` models in `backend/weather/models.py`
- [x] T007 Create migration `backend/weather/migrations/0002_chat.py`
- [x] T008 Add chat/LLM error codes to `backend/weather/errors.py`
- [x] T009 Implement recursive secret redaction in `backend/weather/chat/sanitize.py`
- [x] T010 Implement shared range/city/count validation helpers in `backend/weather/chat/tools.py`
- [x] T011 [P] Add chat request/response serializers to `backend/weather/serializers.py`
- [x] T012 [P] Register `/chat/messages/` in `backend/weather/urls.py`
- [x] T013 Expose `llm_configured` and `llm_model` in `/health/` without the key

--- PHASE 3: User Story 1 - Natural-language queries over stored history (P1) ---
- [x] T014 [US1] Implement `consultar_clima` with row filtering, limit and evidence in `backend/weather/chat/tools.py`
- [x] T015 [US1] Implement `calcular_estadistica` with ORM Avg/Min/Max and evidence in `backend/weather/chat/tools.py`
- [x] T016 [US1] Define the OpenAI-style tool schemas in `backend/weather/chat/tools.py`
- [x] T017 [US1] Implement dispatch that validates JSON arguments and returns errors as tool results
- [x] T018 [US1] Reject missing city/date arguments with `missing_parameter` so the agent asks for clarification
- [x] T019 [US1] Return `no_data: true` and `sample_count: 0` for cities or ranges without rows
- [x] T020 [US1] Write unit tests for tools and aggregation in `backend/weather/tests/unit/test_chat_tools.py`

--- PHASE 4: User Story 2 - Configurable LLM without vendor lock-in (P2) ---
- [x] T021 [US2] Implement the LiteLLM client wrapper with lazy import in `backend/weather/chat/agent.py`
- [x] T022 [US2] Read model/key/base from settings only and map missing credentials to `llm_not_configured`
- [x] T023 [US2] Write the Spanish-answer, no-invention system prompt in `backend/weather/chat/prompts.py`
- [x] T024 [US2] Add contract tests proving a model change needs configuration only in `backend/weather/tests/contract/test_chat.py`

--- PHASE 5: User Story 3 - Persistence and run logging (P2) ---
- [x] T025 [US3] Persist user message, assistant message and tool runs in `backend/weather/chat/agent.py`
- [x] T026 [US3] Run a bounded tool loop (max rounds) and record every call with sanitized args/output
- [x] T027 [US3] Implement `GET /chat/messages/` returning the latest 100 messages oldest-first
- [x] T028 [US3] Implement `POST /chat/messages/` with JSON/same-origin validation and throttle
- [x] T029 [US3] Map tool and LLM failures to a persisted `failed` status with a safe code
- [x] T030 [US3] Test history retention and sanitized tool runs across requests
- [x] T031 [US3] [P] Test duplicate/unknown session handling and invalid UUID rejection

--- PHASE 6: User Story 4 - Accessible FAB + input + history (P3) ---
- [x] T032 [US4] Add chat types in `frontend/src/types/chat.ts`
- [x] T033 [US4] Add `sendChatMessage` and `loadChatHistory` to `frontend/src/api/client.ts`
- [x] T034 [US4] Implement the `useChat` hook with localStorage session id in `frontend/src/hooks/useChat.ts`
- [x] T035 [US4] Implement the FAB + Drawer + input + history + status indicator in `frontend/src/components/ChatPanel.tsx`
- [x] T036 [US4] Show Spanish labels, empty state, failure copy and tool tags without secrets
- [x] T037 [US4] Ensure the panel is operable on narrow viewports (full-width drawer, scrollable history)
- [x] T038 [US4] Mount `<ChatPanel />` in `frontend/src/pages/Dashboard.tsx`
- [x] T039 [US4] Write frontend tests in `frontend/src/components/ChatPanel.test.tsx` and extend MSW handlers

--- FINAL PHASE: Polish & Cross-Cutting Concerns ---
- [x] T040 Update `docs/architecture.md` with the chat flow and `docs/performance.md` with the panel note
- [x] T041 Verify Spanish UI copy and English artifacts/API vocabulary across new files
- [x] T042 Verify `.env.example` contains no real keys or secrets
- [x] T043 Run backend pytest/ruff/mypy and frontend vitest/typecheck/lint; fix findings
- [x] T044 Manually run the quickstart validation scenarios
