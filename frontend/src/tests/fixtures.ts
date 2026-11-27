import type { ChatMessage, ChatTurn } from "../types/chat";
import type {
  CityCandidate,
  CitySnapshot,
  DashboardData,
  Observation,
  PaginatedObservations,
} from "../types/weather";

const santiagoSeries = [
  {
    bucket_start: "2026-11-25T12:00:00Z",
    temperature: 17.2,
    humidity: 64,
    wind_speed: 2.8,
    sample_count: 4,
  },
  {
    bucket_start: "2026-11-25T13:00:00Z",
    temperature: 18.1,
    humidity: 62,
    wind_speed: 3.0,
    sample_count: 4,
  },
];

const valparaisoSeries = [
  {
    bucket_start: "2026-11-25T12:00:00Z",
    temperature: 15.4,
    humidity: 72,
    wind_speed: 5.0,
    sample_count: 3,
  },
  {
    bucket_start: "2026-11-25T13:00:00Z",
    temperature: 16.2,
    humidity: 71,
    wind_speed: 5.4,
    sample_count: 3,
  },
];

export const santiago: CitySnapshot = {
  city: "Santiago",
  city_key: "santiago",
  country_code: "CL",
  source: "live",
  freshness: "current",
  observed_at: "2026-11-25T13:58:00Z",
  age_seconds: 120,
  current: { temperature: 18.4, humidity: 62, wind_speed: 3.1 },
  series: santiagoSeries,
};

export const valparaiso: CitySnapshot = {
  city: "Valparaiso",
  city_key: "valparaiso",
  country_code: "CL",
  source: "live",
  freshness: "current",
  observed_at: "2026-11-25T13:57:00Z",
  age_seconds: 180,
  current: { temperature: 16.2, humidity: 71, wind_speed: 5.4 },
  series: valparaisoSeries,
};

export const dashboardFixture: DashboardData = {
  generated_at: "2026-11-25T14:00:00Z",
  window: "24h",
  bucket: "15m",
  cities: [santiago, valparaiso],
  comparison: {
    temperature_delta: 2.2,
    humidity_delta: -9,
    wind_speed_delta: -2.3,
    warmer_city: "Santiago",
  },
};

export const observations: Observation[] = [
  {
    id: 1043,
    city: "Santiago",
    city_key: "santiago",
    country_code: "CL",
    temperature: 18.6,
    humidity: 61,
    wind_speed: 3.4,
    timestamp: "2026-11-25T14:00:00Z",
  },
  {
    id: 1042,
    city: "Santiago",
    city_key: "santiago",
    country_code: "CL",
    temperature: 18.4,
    humidity: 62,
    wind_speed: 3.1,
    timestamp: "2026-11-25T13:58:00Z",
  },
];

export const observationsFixture: PaginatedObservations = {
  count: 2,
  page: 1,
  page_size: 20,
  total_pages: 1,
  next: null,
  previous: null,
  results: observations,
};

export const candidates: CityCandidate[] = [
  {
    name: "Santiago",
    city_key: "santiago",
    country_code: "CL",
    state: "Region Metropolitana",
    provider_city_id: 3871336,
  },
];

export const chatMessages: ChatMessage[] = [
  {
    id: 1,
    role: "user",
    content: "¿Cuál fue la temperatura promedio en Santiago?",
    status: "completed",
    error_code: null,
    created_at: "2026-11-26T12:00:00Z",
    tool_runs: [],
  },
  {
    id: 2,
    role: "assistant",
    content: "El promedio fue de 18,6 °C sobre 24 observaciones en Santiago.",
    status: "completed",
    error_code: null,
    created_at: "2026-11-26T12:00:05Z",
    tool_runs: [
      {
        name: "calcular_estadistica",
        arguments: { city: "Santiago", metric: "temperature", statistic: "average" },
        output: { ok: true, value: 18.6, sample_count: 24 },
        status: "ok",
        error_code: null,
      },
    ],
  },
];

export const chatTurnFixture: ChatTurn = {
  session_id: "00000000-0000-4000-8000-000000000000",
  message: chatMessages[1],
};

export function chatTurnFor(sessionId: string): ChatTurn {
  return { session_id: sessionId, message: { ...chatMessages[1], id: 2 } };
}
