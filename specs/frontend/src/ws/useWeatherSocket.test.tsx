import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { dashboardFixture } from "../tests/fixtures";
import type { Observation } from "../types/weather";
import { useWeatherSocket } from "./useWeatherSocket";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  close(code = 1000) {
    this.onclose?.({ code } as CloseEvent);
  }

  message(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent<string>);
  }
}

function observation(id: number, timestamp: string): Observation {
  return {
    id,
    city: "Santiago",
    city_key: "santiago",
    country_code: "CL",
    temperature: 19.1,
    humidity: 60,
    wind_speed: 3.2,
    timestamp,
  };
}

describe("useWeatherSocket", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket as unknown as typeof WebSocket);
  });

  it("subscribes with both cities and applies a snapshot", () => {
    const onSnapshot = vi.fn();
    const { result } = renderHook(() =>
      useWeatherSocket({
        cities: ["Santiago", "Valparaiso"],
        enabled: true,
        onSnapshot,
        onObservation: vi.fn(),
      }),
    );

    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].url).toContain("cities=Santiago,Valparaiso");

    act(() => FakeWebSocket.instances[0].onopen?.());
    act(() =>
      FakeWebSocket.instances[0].message({
        type: "snapshot",
        sent_at: "2026-11-25T14:00:00Z",
        payload: dashboardFixture,
      }),
    );

    expect(onSnapshot).toHaveBeenCalledWith(dashboardFixture);
    expect(result.current).toBe("live");
  });

  it("deduplicates observations and ignores stale frames", () => {
    const onObservation = vi.fn();
    renderHook(() =>
      useWeatherSocket({
        cities: ["Santiago", "Valparaiso"],
        enabled: true,
        onSnapshot: vi.fn(),
        onObservation,
      }),
    );

    const socket = FakeWebSocket.instances[0];
    act(() => socket.onopen?.());
    act(() =>
      socket.message({
        type: "snapshot",
        sent_at: "2026-11-25T14:00:00Z",
        payload: dashboardFixture,
      }),
    );

    const stale = observation(1, "2026-11-25T13:57:00Z");
    const fresh = observation(2, "2026-11-25T14:00:00Z");

    act(() => socket.message({ type: "observation", sent_at: fresh.timestamp, payload: stale }));
    act(() => socket.message({ type: "observation", sent_at: fresh.timestamp, payload: fresh }));
    act(() => socket.message({ type: "observation", sent_at: fresh.timestamp, payload: fresh }));

    expect(onObservation).toHaveBeenCalledTimes(1);
    expect(onObservation).toHaveBeenCalledWith(fresh);
  });

  it("reconnects with backoff after an abnormal close", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() =>
      useWeatherSocket({
        cities: ["Santiago", "Valparaiso"],
        enabled: true,
        onSnapshot: vi.fn(),
        onObservation: vi.fn(),
      }),
    );

    const first = FakeWebSocket.instances[0];
    act(() => first.onopen?.());
    act(() => first.onclose?.({ code: 1001 } as CloseEvent));
    expect(result.current).toBe("reconnecting");

    act(() => vi.advanceTimersByTime(1_300));
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it("does not connect while disabled and stays paused", () => {
    const { result } = renderHook(() =>
      useWeatherSocket({
        cities: ["Santiago", "Valparaiso"],
        enabled: false,
        onSnapshot: vi.fn(),
        onObservation: vi.fn(),
      }),
    );

    expect(FakeWebSocket.instances).toHaveLength(0);
    expect(result.current).toBe("paused");
  });
});
