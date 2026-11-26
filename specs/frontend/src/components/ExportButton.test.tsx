import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "../tests/mocks/server";
import { ExportButton } from "./ExportButton";

describe("ExportButton", () => {
  it("downloads the filtered CSV", async () => {
    const user = userEvent.setup();
    render(<ExportButton city="Santiago" window="24h" />);

    await user.click(screen.getByRole("button", { name: /Exportar CSV/ }));
    await waitFor(() => expect(URL.createObjectURL).toHaveBeenCalled());
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("informs the visitor when the export is header-only", async () => {
    server.use(
      http.get("*/weather/export/", () =>
        HttpResponse.text(
          "id,city,country_code,temperature_c,humidity_pct,wind_speed_ms,timestamp\r\n",
          {
            headers: {
              "Content-Type": "text/csv",
              "Content-Disposition": 'attachment; filename="weather-observations.csv"',
            },
          },
        ),
      ),
    );

    const user = userEvent.setup();
    render(<ExportButton window="7d" />);
    await user.click(screen.getByRole("button", { name: /Exportar CSV/ }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "La exportación está vacía: ninguna observación coincide con el filtro actual.",
    );
  });

  it("shows an error when the export fails", async () => {
    server.use(http.get("*/weather/export/", () => new HttpResponse(null, { status: 500 })));

    const user = userEvent.setup();
    render(<ExportButton window="30d" />);
    await user.click(screen.getByRole("button", { name: /Exportar CSV/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No se pudo generar la exportación.",
    );
  });
});
