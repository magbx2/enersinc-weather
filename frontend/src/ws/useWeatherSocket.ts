import { useEffect, useRef, useState } from "react";

import type { DashboardData, Observation, SocketMessage, SocketStatus } from "../types/weather";

const HEARTBEAT_TIMEOUT_MS = 60_000;
const STABILITY_RESET_MS = 10_000;
const MAX_BACKOFF_MS = 30_000;
const MAX_JITTER = 0.2;

export interface WeatherSocketOptions {
  cities: [string, string] | null;
  enabled: boolean;
  onSnapshot: (payload: DashboardData) => void;
  onObservation: (observation: Observation) => void;
  onStatusChange?: (status: SocketStatus) => void;
}

function socketUrl(cities: [string, string]): string {
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const query = cities.map((city) => encodeURIComponent(city)).join(",");
  return `${scheme}://${window.location.host}/ws/weather/?cities=${query}`;
}

export function useWeatherSocket(options: WeatherSocketOptions): SocketStatus {
  const [status, setStatus] = useState<SocketStatus>("paused");
  const callbacks = useRef(options);
  callbacks.current = options;

  const enabled = options.enabled;
  const cityA = options.cities?.[0] ?? "";
  const cityB = options.cities?.[1] ?? "";

  useEffect(() => {
    if (!enabled || !cityA || !cityB) {
      setStatus("paused");
      return;
    }

    let disposed = false;
    let socket: WebSocket | null = null;
    let attempt = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let stabilityTimer: ReturnType<typeof setTimeout> | undefined;
    let deadTimer: ReturnType<typeof setTimeout> | undefined;
    const lastSeen = new Map<string, number>();

    const updateStatus = (next: SocketStatus) => {
      if (disposed) return;
      setStatus(next);
      callbacks.current.onStatusChange?.(next);
    };

    const clearTimer = (timer?: ReturnType<typeof setTimeout>) => {
      if (timer !== undefined) clearTimeout(timer);
    };

    const armDeadTimer = () => {
      clearTimer(deadTimer);
      deadTimer = setTimeout(() => {
        socket?.close(4000, "heartbeat timeout");
      }, HEARTBEAT_TIMEOUT_MS);
    };

    const scheduleReconnect = () => {
      if (disposed) return;
      const base = Math.min(MAX_BACKOFF_MS, 1000 * 2 ** Math.min(attempt, 5));
      const jitter = base * MAX_JITTER * Math.random();
      attempt += 1;
      updateStatus("reconnecting");
      reconnectTimer = setTimeout(connect, base + jitter);
    };

    const handleMessage = (event: MessageEvent<string>) => {
      armDeadTimer();
      let message: SocketMessage;
      try {
        message = JSON.parse(event.data) as SocketMessage;
      } catch {
        return;
      }

      if (message.type === "snapshot") {
        lastSeen.clear();
        for (const city of message.payload.cities) {
          const observed = city.observed_at ? Date.parse(city.observed_at) : 0;
          lastSeen.set(city.city_key, Number.isNaN(observed) ? 0 : observed);
        }
        updateStatus("live");
        callbacks.current.onSnapshot(message.payload);
        return;
      }

      if (message.type === "observation") {
        const observed = Date.parse(message.payload.timestamp);
        const previous = lastSeen.get(message.payload.city_key) ?? 0;
        if (!Number.isNaN(observed) && observed <= previous) return;
        if (!Number.isNaN(observed)) lastSeen.set(message.payload.city_key, observed);
        callbacks.current.onObservation(message.payload);
        return;
      }

      if (message.type === "heartbeat") {
        updateStatus("live");
        return;
      }

      if (message.type === "error") {
        updateStatus("paused");
      }
    };

    const connect = () => {
      if (disposed) return;
      updateStatus(attempt === 0 ? "connecting" : "reconnecting");
      socket = new WebSocket(socketUrl([cityA, cityB]));
      socket.onopen = () => {
        armDeadTimer();
        clearTimer(stabilityTimer);
        stabilityTimer = setTimeout(() => {
          attempt = 0;
        }, STABILITY_RESET_MS);
      };
      socket.onmessage = handleMessage;
      socket.onclose = (event) => {
        clearTimer(deadTimer);
        clearTimer(stabilityTimer);
        if (disposed || event.code === 1000 || event.code === 4001) {
          updateStatus("paused");
          return;
        }
        scheduleReconnect();
      };
    };

    connect();

    return () => {
      disposed = true;
      clearTimer(reconnectTimer);
      clearTimer(stabilityTimer);
      clearTimer(deadTimer);
      socket?.close(1000, "client unmount");
      socket = null;
    };
  }, [enabled, cityA, cityB]);

  return status;
}
