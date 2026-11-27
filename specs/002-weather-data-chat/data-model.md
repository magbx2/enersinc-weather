# Phase 1 Data Model: Weather Data Chat

**Feature**: 002-weather-data-chat | **Date**: 2026-11-26

## New entities

### ChatSession

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID (primary key) | client-generated UUID v4 | `weather-chat-session` in `localStorage`; not an auth token |
| `created_at` | datetime | auto | UTC |
| `updated_at` | datetime | auto | bumped on every message |

Index: primary key only.

### ChatMessage

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | bigint | PK | |
| `session` | FK → ChatSession | `on_delete=CASCADE`, indexed | |
| `role` | char(9) | `user` or `assistant` | |
| `content` | text | user input max 2000; assistant truncated at 8000 | Spanish assistant text; user text echoed |
| `status` | char(11) | `completed` or `failed` | user messages are always `completed` |
| `error_code` | char(40) | nullable | English machine code, e.g. `llm_not_configured` |
| `created_at` | datetime | auto, indexed | UTC |

Ordering: `created_at`, `id` ascending for display. API returns the latest 100.

### ToolRun

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | bigint | PK | |
| `message` | FK → ChatMessage | `on_delete=CASCADE`, related name `tool_runs` | assistant message that used it |
| `name` | char(40) | `consultar_clima` or `calcular_estadistica` | |
| `arguments` | JSON | sanitized | validated arguments as executed |
| `output` | JSON | sanitized | tool result including `evidence` |
| `status` | char(8) | `ok` or `error` | |
| `error_code` | char(40) | nullable | e.g. `missing_parameter`, `invalid_range`, `no_data_available` |
| `created_at` | datetime | auto | UTC |

## Relationships

```text
ChatSession 1 ──── * ChatMessage 1 ──── * ToolRun
WeatherData (existing, read-only for chat tools)
```

## Existing entity used by the tools

`WeatherData`: `city`, `city_key`, `country_code`, `temperature`, `humidity`, `wind_speed`,
`timestamp`, `id`. The tools filter by `city_key` and `timestamp` and aggregate with ORM
`Avg`/`Min`/`Max`; no chat entity duplicates weather values.

## State rules

- A session is created on the first message for a UUID; an invalid UUID is rejected with
  `invalid_chat` (HTTP 400).
- An assistant message is created when processing starts (`status` placeholder in memory) and
  persisted once with its final status, so a failed run is visible in history.
- `ToolRun` rows are written for every executed call, including errors, with sanitized payloads.
- History retention is indefinite in this microspec; no purge job.
- `ChatSession.updated_at` drives future cleanup jobs but no cleanup is in scope.
