import { http, HttpResponse } from "msw";

import { candidates, dashboardFixture, observationsFixture } from "../fixtures";

export const handlers = [
  http.get("*/dashboard-data/", () => HttpResponse.json(dashboardFixture)),
  http.post("*/weather/refresh/", () => HttpResponse.json(dashboardFixture)),
  http.get("*/cities/search/", ({ request }) => {
    const query = new URL(request.url).searchParams.get("q")?.toLowerCase() ?? "";
    if (query.includes("nowhere")) {
      return HttpResponse.json({ results: [] });
    }
    return HttpResponse.json({ results: candidates });
  }),
  http.get("*/weather/export/", () =>
    HttpResponse.text(
      'id,city,country_code,temperature_c,humidity_pct,wind_speed_ms,timestamp\r\n1043,Santiago,CL,18.60,61,3.40,2026-11-25T14:00:00Z\r\n',
      { headers: { "Content-Type": "text/csv", "Content-Disposition": 'attachment; filename="weather.csv"' } },
    ),
  ),
  http.get("*/weather/", () => HttpResponse.json(observationsFixture)),
];
