import type {
  ApiErrorEnvelope,
  CityCandidate,
  CitySnapshot,
  DashboardData,
  Observation,
  PaginatedObservations,
  Window,
} from "../types/weather";

export class ApiRequestError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;

  constructor(
    message: string,
    code: string,
    status: number,
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiRequestError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

function toQuery(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let envelope: ApiErrorEnvelope | null = null;
    try {
      envelope = (await response.json()) as ApiErrorEnvelope;
    } catch {
      envelope = null;
    }
    throw new ApiRequestError(
      envelope?.error.message ?? `La solicitud falló con el estado ${response.status}.`,
      envelope?.error.code ?? "internal_error",
      response.status,
      envelope?.error.details ?? {},
    );
  }

  return (await response.json()) as T;
}

export interface ExportParams {
  city?: string;
  window: Window;
}

export interface ExportResult {
  content: string;
  filename: string;
  empty: boolean;
}

export const api = {
  dashboardData(
    cities: [string, string] | null,
    window: Window,
    options: { signal?: AbortSignal; refresh?: boolean } = {},
  ): Promise<DashboardData> {
    return request(
      `/dashboard-data/${toQuery({
        cities: cities ? cities.join(",") : undefined,
        window,
        refresh: options.refresh,
      })}`,
      { signal: options.signal },
    );
  },

  refreshWeather(cities: [string, string]): Promise<DashboardData> {
    return request("/weather/refresh/", {
      method: "POST",
      body: JSON.stringify({ cities }),
    });
  },

  listObservations(
    params: {
      page?: number;
      pageSize?: number;
      city?: string;
      start?: string;
      end?: string;
    },
    signal?: AbortSignal,
  ): Promise<PaginatedObservations> {
    return request(
      `/weather/${toQuery({
        page: params.page,
        page_size: params.pageSize,
        city: params.city,
        start: params.start,
        end: params.end,
      })}`,
      { signal },
    );
  },

  searchCities(query: string, limit = 5, signal?: AbortSignal): Promise<CityCandidate[]> {
    return request<{ results: CityCandidate[] }>(`/cities/search/${toQuery({ q: query, limit })}`, {
      signal,
    }).then((payload) => payload.results);
  },

  async exportCsv(params: ExportParams, signal?: AbortSignal): Promise<ExportResult> {
    const response = await fetch(
      `/weather/export/${toQuery({ city: params.city, window: params.window })}`,
      { signal, headers: { Accept: "text/csv" } },
    );
    if (!response.ok) {
      throw new ApiRequestError(
        "No se pudo generar la exportación.",
        "internal_error",
        response.status,
      );
    }
    const content = await response.text();
    const disposition = response.headers.get("content-disposition") ?? "";
    const match = /filename="?([^";]+)"?/i.exec(disposition);
    const lines = content.trim().split(/\r?\n/);
    return {
      content,
      filename: match?.[1] ?? "weather-observations.csv",
      empty: lines.length <= 1,
    };
  },
};

export function snapshotCity(data: DashboardData, cityKey: string): CitySnapshot | undefined {
  return data.cities.find((city) => city.city_key === cityKey);
}

export function withObservation(data: DashboardData, observation: Observation): DashboardData {
  const cities = data.cities.map((city) => {
    if (city.city_key !== observation.city_key) return city;
    return {
      ...city,
      city: observation.city,
      country_code: observation.country_code,
      source: "live" as const,
      freshness: "current" as const,
      observed_at: observation.timestamp,
      age_seconds: 0,
      current: {
        temperature: observation.temperature,
        humidity: observation.humidity,
        wind_speed: observation.wind_speed,
      },
    };
  });
  return { ...data, cities };
}
