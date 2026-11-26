import { describe, expect, it } from "vitest";

import { formatAge, formatTimestamp, isStale, relativeAge, signed } from "./time";

describe("time helpers", () => {
  it("formats known ages in seconds, minutes, hours and days", () => {
    expect(formatAge(0)).toBe("hace 0s");
    expect(formatAge(59)).toBe("hace 59s");
    expect(formatAge(120)).toBe("hace 2m");
    expect(formatAge(7_200)).toBe("hace 2h");
    expect(formatAge(172_800)).toBe("hace 2d");
    expect(formatAge(null)).toBe("no disponible");
  });

  it("computes relative age from an ISO timestamp", () => {
    const now = new Date("2026-11-25T14:00:00Z");
    expect(relativeAge("2026-11-25T13:58:00Z", now)).toBe("hace 2m");
    expect(relativeAge(null, now)).toBe("no disponible");
    expect(relativeAge("not-a-date", now)).toBe("no disponible");
  });

  it("detects stale readings around the 60 second window", () => {
    const now = new Date("2026-11-25T14:00:00Z");
    expect(isStale("2026-11-25T13:59:30Z", now)).toBe(false);
    expect(isStale("2026-11-25T13:58:00Z", now)).toBe(true);
    expect(isStale(null, now)).toBe(true);
  });

  it("formats signed deltas and invalid timestamps", () => {
    expect(signed(2.25)).toBe("+2.3");
    expect(signed(-2.25)).toBe("-2.3");
    expect(signed(null)).toBe("—");
    expect(formatTimestamp("not-a-date")).toBe("Hora no válida");
    expect(formatTimestamp(null)).toBe("Sin observación");
  });
});
