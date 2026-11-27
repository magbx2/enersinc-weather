# Phase 1 Data Model: Two-City Weather Comparison Dashboard

## Overview

The persisted model is deliberately small: a single append-only table of weather observations.
Current comparisons, charts, and CSV exports are all derived from this table, so every displayed
number can be traced to a stored row. There is no separate `City` table; city identity is
denormalized into each observation, and a normalized `city_key` provides stable filtering and
indexing. The provider's numeric city identifier is available only while searching (`CityCandidate`)
and is not persisted, so two same-named cities in different countries share a `city_key` in this
delivery.

## Entity: WeatherData

One recorded reading for one city at one provider timestamp.

| Field | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | bigint, identity, PK | no | auto | Surrogate key used for diagnostics and as the stable row reference in CSV exports; not a user-facing city identifier |
| `city` | varchar(120) | no | — | Display name exactly as resolved by the provider, e.g. `Santiago` |
| `city_key` | varchar(120) | no | — | Normalized key: lowercase, trimmed, internal whitespace collapsed, diacritics folded; used by filters and cache keys |
| `country_code` | char(2) | yes | `null` | ISO 3166-1 alpha-2, displayed with the reading; it does not participate in the `city_key` uniqueness key |
| `temperature` | numeric(5,2) | no | — | Degrees Celsius |
| `humidity` | smallint | no | — | Relative humidity percentage |
| `wind_speed` | numeric(5,2) | no | — | Meters per second |
| `timestamp` | timestamptz | no | — | Provider observation time, stored in UTC |
| `created_at` | timestamptz | no | now | Row insertion time in UTC; used for diagnostics only |

### Constraints

| Name | Rule | Purpose |
|---|---|---|
| `uq_weather_city_timestamp` | `UNIQUE (city_key, timestamp)` | Deduplicates repeated provider polls of the same reading |
| `ck_weather_humidity` | `humidity BETWEEN 0 AND 100` | Rejects impossible values |
| `ck_weather_wind_nonneg` | `wind_speed >= 0` | Rejects negative wind speed |
| `ck_weather_temperature` | `temperature BETWEEN -100 AND 70` | Rejects unit mistakes and provider glitches |
| `ck_weather_city_key` | `length(city_key) BETWEEN 1 AND 120` | Guards empty or oversized keys |

### Indexes

| Index | Columns | Serves |
|---|---|---|
| `ix_weather_city_ts_desc` | `(city_key, timestamp DESC)` | City-filtered table pages, per-city latest row, per-city series |
| `ix_weather_ts_desc` | `(timestamp DESC)` | Unfiltered table pages, recent-activity selection for the scheduler |
| `ix_weather_city` | `(city_key)` | Distinct city listing in the filter control |

### Validation rules (from requirements)

- `city` and `city_key` are derived from a provider geocoding result; client-supplied names are only
  used as a search query and are never stored verbatim without resolution.
- `city` input: trimmed, 1–80 characters, pattern `^[\p{L}][\p{L} .'-]*$`, no control characters,
  no markup. Invalid input yields a 400 with `code: "invalid_city"`.
- `humidity`, `temperature`, `wind_speed` must be finite numbers; `NaN` and `Infinity` are rejected.
- `timestamp` must be within the last 24 hours and no more than 10 minutes in the future.
- Two selected cities must be distinct after normalization; otherwise 400 `code: "duplicate_city"`.
- `uq_weather_city_timestamp` is scoped to `(city_key, timestamp)` only. `country_code` is kept for
  display and diagnostics but does not participate in the uniqueness key, so same-name cities in
  different countries are not separated.

### Lifecycle

Rows are append-only. There are no updates or deletes in the feature scope, so there is no state
machine. Retention is indefinite per the spec's assumptions; no pruning job exists.

## Derived (non-persisted) structures

| Structure | Composition | Rebuild source |
|---|---|---|
| Current reading | Newest `WeatherData` row per city, wrapped with `source` (`live`/`stale`) and `age_seconds` | Cache `weather:current:v1:{city_key}`, else database |
| Search candidate | `name`, `city_key`, `country_code`, `state`, `provider_city_id` | Redis geocoding cache, else stored cities, else OpenWeather geocoding |
| Default comparison pair | The two cities with the most recent stored observation, newest first (zero, one or two) | PostgreSQL `MAX(timestamp)` per `city_key` |
| Series point | `bucket_start`, `temperature_avg`, `humidity_avg`, `wind_speed_avg`, `sample_count` | `date_trunc` aggregate over `WeatherData` filtered by window |
| Comparison summary | Per-metric absolute and signed difference between the two latest readings | Two current readings |
| Freshness status | `current` when `age_seconds <= 60`, otherwise `stale`; `unavailable` when no row exists | Observation timestamp vs server clock |
| Paginated page | `count`, `next`, `previous`, `results[]` | `LIMIT/OFFSET` over filtered rows |

## Bucket granularity by window

| Window | Bucket | Maximum points per series |
|---|---|---|
| 24h | 15 minutes | 96 |
| 7d | 2 hours | 84 |
| 30d | 12 hours | 60 |

Buckets are computed in UTC and returned as ISO 8601 timestamps; empty buckets are omitted rather
than zero-filled, so charts show gaps instead of invented values.

## Relationship to other features

The future agent chat (separate microspec) will read `WeatherData` through purpose-built, typed
queries. It MUST NOT receive direct table access and MUST NOT generate SQL. No schema change is
reserved for it beyond what is defined here.

## Indexing and volume estimate

Two tracked cities at two observations per minute produce about 2.1 million rows per year. At that
volume the `(city_key, timestamp DESC)` index keeps filtered page reads and latest-row lookups
sub-millisecond while using well under a gigabyte of storage, so no partitioning or archival is
required for this delivery.
