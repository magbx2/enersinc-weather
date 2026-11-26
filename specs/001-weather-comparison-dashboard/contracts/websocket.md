# WebSocket Contract: Live Weather Updates

## Endpoint

```text
GET /ws/weather/?cities=<city-a>,<city-b>
```

Same origin as the dashboard, so the browser uses `ws://` or `wss://` based on the page scheme.
The endpoint accepts no request body and no client-authored data beyond the query parameter and
`ping` frames.

## Subscription rules

- `cities` is required and MUST contain exactly two comma-separated city names, 1–80 characters
  each, distinct after normalization.
- Names are normalized with the same rules as the REST API; unknown names are rejected.
- Invalid input closes the socket with code `4001` and an `error` frame.
- Group membership is one group per city: `weather.{city_key}`.
- A connection is removed from all groups on disconnect; no cleanup job is required.

## Message envelope

Every server frame is JSON:

```json
{
  "type": "observation",
  "sent_at": "2026-11-25T14:00:02Z",
  "payload": { }
}
```

| Field | Type | Notes |
|---|---|---|
| `type` | string | `snapshot`, `observation`, `heartbeat` or `error` |
| `sent_at` | string (ISO 8601 UTC) | Server emission time |
| `payload` | object | Shape depends on `type` |

## `snapshot`

Sent immediately after a successful subscription so the client can render without a second fetch.

```json
{
  "type": "snapshot",
  "sent_at": "2026-11-25T14:00:00Z",
  "payload": {
    "window": "24h",
    "cities": [
      {
        "city": "Santiago",
        "city_key": "santiago",
        "source": "live",
        "freshness": "current",
        "observed_at": "2026-11-25T13:58:00Z",
        "age_seconds": 120,
        "current": { "temperature": 18.4, "humidity": 62, "wind_speed": 3.1 }
      },
      {
        "city": "Valparaiso",
        "city_key": "valparaiso",
        "source": "stale",
        "freshness": "stale",
        "observed_at": "2026-11-25T13:40:00Z",
        "age_seconds": 1200,
        "current": { "temperature": 16.2, "humidity": 71, "wind_speed": 5.4 }
      }
    ],
    "comparison": {
      "temperature_delta": 2.2,
      "humidity_delta": -9,
      "wind_speed_delta": -2.3,
      "warmer_city": "Santiago"
    }
  }
}
```

`current` is `null` when a city has no stored observation at all; `freshness` is then
`unavailable`.

## `observation`

Sent after `WeatherData` is committed for a subscribed city. The payload uses the same observation
shape as `GET /weather/`.

```json
{
  "type": "observation",
  "sent_at": "2026-11-25T14:00:02Z",
  "payload": {
    "id": 1043,
    "city": "Santiago",
    "city_key": "santiago",
    "country_code": "CL",
    "temperature": 18.6,
    "humidity": 61,
    "wind_speed": 3.4,
    "timestamp": "2026-11-25T14:00:00Z",
    "source": "live"
  }
}
```

Clients MUST deduplicate by `(city_key, timestamp)` and MUST ignore events older than the currently
displayed reading for that city.

## `heartbeat`

Sent every 25 seconds on an idle connection.

```json
{
  "type": "heartbeat",
  "sent_at": "2026-11-25T14:00:25Z",
  "payload": { "cities": ["santiago", "valparaiso"] }
}
```

If no frame of any type arrives for 60 seconds, the client considers the connection dead and
starts reconnection.

## `error`

```json
{
  "type": "error",
  "sent_at": "2026-11-25T14:00:00Z",
  "payload": {
    "code": "invalid_subscription",
    "message": "Exactly two distinct cities are required."
  }
}
```

Error codes: `invalid_subscription`, `unknown_city`, `duplicate_city`, `internal_error`.

## Close codes

| Code | Meaning | Client action |
|---|---|---|
| `1000` | Normal closure (page unload) | Do not reconnect |
| `1001` | Server going away (restart) | Reconnect with backoff |
| `1011` | Server error | Reconnect with backoff |
| `4001` | Invalid subscription | Do not reconnect; show a validation message |

## Client reconnection policy

- Attempt reconnection with exponential backoff: 1 s, 2 s, 4 s, 8 s, 16 s, capped at 30 s.
- Add up to 20% jitter to avoid synchronized reconnects.
- Reset the backoff after a connection stays open for 10 seconds.
- On reconnect, the server's `snapshot` replaces local state, which removes missed-event gaps.
- While disconnected, the UI shows a "live updates paused" indicator and keeps working from the
  last known data.

## Server-side delivery guarantees

- Events are emitted only after the database transaction commits, so a client never renders a row
  that was rolled back.
- Delivery is at-most-once per connection; missed events are recovered by the next `snapshot` or a
  REST refetch. No durable event log is maintained.
- A slow client does not block inserts: group sends use Channels' asynchronous layer, and the
  producer never waits on a browser.
