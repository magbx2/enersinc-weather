# Typed Tool Contract: Weather Data Chat

**Feature**: 002-weather-data-chat | **Version**: 1.0.0

Both tools read only `WeatherData` rows through the Django ORM. They never accept SQL, shell
commands, URLs or arbitrary field names. `city` is mandatory; a call without it returns
`missing_parameter` and the agent must ask the user to clarify instead of inventing a city.

## Shared evidence object

Every successful result includes:

```json
{
  "evidence": {
    "tool": "consultar_clima",
    "city": "Buenos Aires",
    "city_key": "buenos aires",
    "filters": { "start": "2026-08-01T00:00:00Z", "end": "2026-09-01T00:00:00Z" },
    "sample_count": 124,
    "source": "weather_data"
  }
}
```

`sample_count` is the number of database rows used. `source` is always `weather_data` so the model
can state where the answer came from.

## `consultar_clima`

Returns stored rows for one city in `[start, end)`, newest first.

```json
{
  "type": "function",
  "function": {
    "name": "consultar_clima",
    "description": "Read stored weather observations for one city in a date range.",
    "parameters": {
      "type": "object",
      "additionalProperties": false,
      "required": ["city"],
      "properties": {
        "city": { "type": "string", "minLength": 1, "maxLength": 80 },
        "start": { "type": "string", "description": "ISO 8601 date or date-time, inclusive lower bound in UTC." },
        "end": { "type": "string", "description": "ISO 8601 date or date-time, exclusive upper bound in UTC." },
        "limit": { "type": "integer", "minimum": 1, "maximum": 100, "default": 20 }
      }
    }
  }
}
```

Success:

```json
{
  "ok": true,
  "evidence": { "...": "..." },
  "total_matched": 124,
  "returned": 20,
  "no_data": false,
  "rows": [
    { "id": 1043, "temperature": 18.6, "humidity": 61, "wind_speed": 3.4, "timestamp": "2026-11-25T14:00:00Z" }
  ]
}
```

No rows: `ok: true`, `no_data: true`, `total_matched: 0`, `rows: []`.

Errors (returned as `{ok:false,error:{code,message,evidence}}`): `missing_parameter`,
`invalid_city`, `invalid_range`, `invalid_limit`, `unknown_city`, `database_error`.

## `calcular_estadistica`

Computes an aggregate with the ORM (`Avg`, `Min`, `Max`). Arithmetic never happens in the model.

```json
{
  "type": "function",
  "function": {
    "name": "calcular_estadistica",
    "description": "Compute an aggregate for one metric over stored weather observations.",
    "parameters": {
      "type": "object",
      "additionalProperties": false,
      "required": ["city", "metric", "statistic"],
      "properties": {
        "city": { "type": "string", "minLength": 1, "maxLength": 80 },
        "metric": { "type": "string", "enum": ["temperature", "humidity", "wind_speed"] },
        "statistic": { "type": "string", "enum": ["average", "minimum", "maximum"] },
        "start": { "type": "string" },
        "end": { "type": "string" }
      }
    }
  }
}
```

Success:

```json
{
  "ok": true,
  "evidence": { "...": "...", "metric": "temperature", "statistic": "average", "unit": "celsius" },
  "value": 17.42,
  "sample_count": 124,
  "no_data": false
}
```

No rows: `ok: true`, `no_data: true`, `value: null`, `sample_count: 0`.

Errors: `missing_parameter`, `invalid_city`, `invalid_metric`, `invalid_statistic`,
`invalid_range`, `unknown_city`, `database_error`.

## Execution rules

1. Validate the JSON arguments before touching the database. Unknown keys are rejected.
2. Normalize `city` with the existing `normalize_city` boundary validator.
3. Resolve the effective range; when both bounds are absent use the last 30 days and report them
   in `evidence.filters`.
4. Query only `WeatherData` with the ORM; request no raw SQL.
5. Cap rows at 100; never return the whole table.
6. Return the evidence object on both success and error paths (filters already applied, if any).
7. The agent may call tools at most `LLM_MAX_TOOL_ROUNDS` times per turn.
