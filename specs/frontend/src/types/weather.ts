export type Window = "24h" | "7d" | "30d";
export type Freshness = "current" | "stale" | "unavailable";
export type Source = "live" | "stale";

export interface CurrentReading {
  temperature: number;
  humidity: number;
  wind_speed: number;
}

export interface SeriesPoint {
  bucket_start: string;
  temperature: number;
  humidity: number;
  wind_speed: number;
  sample_count: number;
}

export interface CitySnapshot {
  city: string;
  city_key: string;
  country_code?: string | null;
  source: Source;
  freshness: Freshness;
  observed_at: string | null;
  age_seconds: number | null;
  current: CurrentReading | null;
  series: SeriesPoint[];
  reason?: string;
}

export interface ComparisonSummary {
  temperature_delta: number | null;
  humidity_delta: number | null;
  wind_speed_delta: number | null;
  warmer_city: string | null;
}

export interface DashboardData {
  generated_at: string;
  window: Window;
  bucket: "15m" | "2h" | "12h";
  cities: CitySnapshot[];
  comparison: ComparisonSummary;
}

export interface Observation {
  id: number;
  city: string;
  city_key: string;
  country_code: string | null;
  temperature: number;
  humidity: number;
  wind_speed: number;
  timestamp: string;
}

export interface PaginatedObservations {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: Observation[];
}

export interface CityCandidate {
  name: string;
  city_key: string;
  country_code: string;
  state: string | null;
  provider_city_id: number;
}

export interface Health {
  status: "ok" | "degraded" | "down";
  database: "up" | "down";
  cache: "up" | "down";
  provider_configured: boolean;
  scheduler: "up" | "unknown";
  version: string;
}

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
    request_id: string;
  };
}

export type SocketStatus = "connecting" | "live" | "paused" | "reconnecting";

export type SocketMessage =
  | { type: "snapshot"; sent_at: string; payload: DashboardData }
  | { type: "observation"; sent_at: string; payload: Observation & { source: Source } }
  | { type: "heartbeat"; sent_at: string; payload: { cities: string[] } }
  | { type: "error"; sent_at: string; payload: { code: string; message: string } };
