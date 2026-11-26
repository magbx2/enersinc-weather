import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { dashboardFixture } from "../tests/fixtures";
import { server } from "../tests/mocks/server";
import { Dashboard } from "./Dashboard";

class NoopWebSocket {
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(readonly url: string) {}

  close() {}
}

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

interface CapturedRequest {
  cities: string | null;
  window: string | null;
}

function captureDashboardRequests(): CapturedRequest[] {
  const requests: CapturedRequest[] = [];
  server.use(
    http.get("*/dashboard-data/", ({ request }) => {
      const url = new URL(request.url);
      requests.push({
        cities: url.searchParams.get("cities"),
        window: url.searchParams.get("window"),
      });
      return HttpResponse.json(dashboardFixture);
    }),
  );
  return requests;
}

describe("Dashboard", () => {
  beforeEach(() => {
    vi.stubGlobal("WebSocket", NoopWebSocket as unknown as typeof WebSocket);
  });

  it("loads the stored defaults on / and reflects them in the URL", async () => {
    const requests = captureDashboardRequests();

    renderAt("/");

    await waitFor(() => {
      expect(requests[0]?.cities).toBeNull();
    });
    await waitFor(() => {
      expect(requests.some(({ cities }) => cities === "Santiago,Valparaiso")).toBe(true);
    });
    expect(await screen.findByText(/Diferencia \(Santiago/)).toBeInTheDocument();
  });

  it("keeps explicit URL cities and does not request defaults", async () => {
    const requests = captureDashboardRequests();

    renderAt("/?city_a=Bogota&city_b=Madrid");

    await waitFor(() => {
      expect(requests.some(({ cities }) => cities === "Bogota,Madrid")).toBe(true);
    });
    expect(requests.every(({ cities }) => cities === "Bogota,Madrid")).toBe(true);
  });

  it("shows the empty comparison when PostgreSQL has no stored cities", async () => {
    server.use(
      http.get("*/dashboard-data/", () =>
        HttpResponse.json({
          ...dashboardFixture,
          cities: [],
          comparison: {
            temperature_delta: null,
            humidity_delta: null,
            wind_speed_delta: null,
            warmer_city: null,
          },
        }),
      ),
    );

    renderAt("/");

    expect(
      await screen.findByText(/Elige dos ciudades para comparar su tiempo/),
    ).toBeInTheDocument();
  });
});
