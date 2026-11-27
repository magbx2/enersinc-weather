# Quickstart: Weather Data Chat

**Feature**: 002-weather-data-chat

## 1. Start the stack

```bash
docker compose up --build
```

The backend image now installs `litellm`. Existing weather behaviour is unchanged.

## 2. Configure the model (optional)

Copy the example file and set a provider model plus its key:

```bash
cp .env.example .env
```

```dotenv
# Any LiteLLM model identifier. Changing this changes provider/model with no code change.
LLM_MODEL=gpt-4o-mini
# Key for the selected provider. Leave empty to use the provider SDK's own env key.
LLM_API_KEY=YOUR_KEY
# Optional OpenAI-compatible gateway.
LLM_API_BASE=
```

With no key, the app still boots. The chat panel shows a Spanish "El asistente no está
configurado" state; weather features are unaffected.

## 3. Use the assistant

1. Open <http://localhost:8000/>.
2. Click the floating chat button (bottom-right).
3. The header shows the run status and the configured model (`configurado` / `no configurado`).
4. Ask, for example:
   - `¿Cuál fue la temperatura promedio en Santiago en los últimos 7 días?`
   - `Muéstrame las últimas 10 lecturas de Valparaíso.`
   - `¿Cuál fue la humedad mínima en Madrid en agosto?`
5. Each answer shows the tool names used, the filters and the sample count.
6. Reload the page: the same history and tool runs are restored from PostgreSQL.

## 4. Verify

```bash
# Health now reports the configured model (never the key).
curl -s http://localhost:8000/health/ | jq '.llm'

# History for a session (use the id shown by the panel / localStorage).
curl -s "http://localhost:8000/chat/messages/?session_id=$SESSION_ID" | jq

# Send a message directly (same-origin marker required).
curl -s -X POST http://localhost:8000/chat/messages/ \
  -H 'Content-Type: application/json' -H 'Origin: http://localhost:8000' \
  -d '{"session_id":"'"$SESSION_ID"'","message":"¿Cuál fue la temperatura promedio en Santiago?"}' | jq
```

## 5. Quality gates

```bash
docker compose run --rm backend pytest
docker compose run --rm backend ruff check .
docker compose run --rm backend mypy
docker compose run --rm --entrypoint npm frontend run test -- --run
docker compose run --rm --entrypoint npm frontend run typecheck
docker compose run --rm --entrypoint npm frontend run lint
```

## Validation scenarios

| # | Scenario | Expected |
|---|---|---|
| 1 | Ask for an average with a city and range | Spanish answer, backend-computed value, evidence with sample count |
| 2 | Ask with no city | Clarification request, no invented city |
| 3 | Ask about a city with no stored rows | Honest "no hay datos" answer |
| 4 | Change `LLM_MODEL` to another provider and restart | Answers keep working with no code change |
| 5 | No key configured | Visible safe failure state, stack healthy but chat degraded |
| 6 | Reload after several turns | Identical messages and tool runs restored |
| 7 | Trigger a tool error | Visible failed status with Spanish copy, no secrets in log |
