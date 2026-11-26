import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { dashboardFixture } from "../tests/fixtures";
import { HistoryCharts } from "./HistoryCharts";

describe("HistoryCharts", () => {
  it("renders both city series and lets the visitor switch windows", async () => {
    const onWindowChange = vi.fn();
    const user = userEvent.setup();
    render(
      <HistoryCharts
        cities={dashboardFixture.cities}
        window="24h"
        onWindowChange={onWindowChange}
      />,
    );

    expect(screen.getByText("Santiago")).toBeInTheDocument();
    expect(screen.getByText("Valparaiso")).toBeInTheDocument();
    expect(screen.getAllByText("2 intervalos", { exact: false })).toHaveLength(2);

    await user.click(screen.getByText("7 días"));
    expect(onWindowChange).toHaveBeenCalledWith("7d");
  });

  it("renders a single series when the table is filtered to one city", () => {
    render(
      <HistoryCharts cities={[dashboardFixture.cities[0]]} window="24h" onWindowChange={vi.fn()} />,
    );

    expect(screen.getByText("Santiago")).toBeInTheDocument();
    expect(screen.queryByText("Valparaiso")).not.toBeInTheDocument();
  });

  it("shows a distinct empty state when no history exists yet", () => {
    render(
      <HistoryCharts
        cities={[
          { ...dashboardFixture.cities[0], series: [] },
          { ...dashboardFixture.cities[1], series: [] },
        ]}
        window="24h"
        onWindowChange={vi.fn()}
      />,
    );

    expect(screen.getByText(/Aún no hay historial almacenado/)).toBeInTheDocument();
  });

  it("asks for two cities before rendering the charts", () => {
    render(<HistoryCharts window="7d" onWindowChange={vi.fn()} />);
    expect(screen.getByText(/Elige dos ciudades para explorar su historial/)).toBeInTheDocument();
  });

  it("shows a loading skeleton and an error with retry", async () => {
    const onRetry = vi.fn();
    const { rerender } = render(<HistoryCharts window="24h" onWindowChange={vi.fn()} isLoading />);
    expect(screen.getByLabelText("Cargando gráficos del historial")).toBeInTheDocument();

    rerender(
      <HistoryCharts
        window="24h"
        onWindowChange={vi.fn()}
        error={new Error("offline")}
        onRetry={onRetry}
      />,
    );
    expect(
      screen.getByText(/No se pudieron cargar los gráficos del historial/),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
