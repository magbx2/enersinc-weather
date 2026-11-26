import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { dashboardFixture, santiago, valparaiso } from "../tests/fixtures";
import { CurrentComparison } from "./CurrentComparison";

describe("CurrentComparison", () => {
  it("renders three metrics per city, signed deltas and observation times", () => {
    render(<CurrentComparison data={dashboardFixture} />);

    const temperatures = screen.getAllByText("Temperatura");
    expect(temperatures).toHaveLength(2);
    expect(temperatures[0].closest(".ant-statistic")).toHaveTextContent("18.4°C");
    expect(temperatures[1].closest(".ant-statistic")).toHaveTextContent("16.2°C");

    const humidities = screen.getAllByText("Humedad");
    expect(humidities[0].closest(".ant-statistic")).toHaveTextContent("62%");
    expect(humidities[1].closest(".ant-statistic")).toHaveTextContent("71%");

    const winds = screen.getAllByText("Velocidad del viento");
    expect(winds[0].closest(".ant-statistic")).toHaveTextContent("3.1m/s");
    expect(winds[1].closest(".ant-statistic")).toHaveTextContent("5.4m/s");

    expect(
      screen.getByText("Diferencia de temperatura").closest(".ant-statistic"),
    ).toHaveTextContent("+2.2°C");
    expect(screen.getByText("Diferencia de humedad").closest(".ant-statistic")).toHaveTextContent(
      "-9pp",
    );
    expect(screen.getByText("Diferencia de viento").closest(".ant-statistic")).toHaveTextContent(
      "-2.3m/s",
    );
    expect(screen.getAllByText(/Medido/)).toHaveLength(2);
    expect(screen.getByText("Ciudad más cálida:")).toBeInTheDocument();
  });

  it("shows the loading skeleton while fetching", () => {
    render(<CurrentComparison isLoading />);
    expect(screen.getByLabelText("Cargando comparación")).toBeInTheDocument();
  });

  it("shows an instructive empty state before cities are chosen", () => {
    render(<CurrentComparison />);
    expect(screen.getByText(/Elige dos ciudades para comparar su tiempo/)).toBeInTheDocument();
  });

  it("shows an error with a retry action", async () => {
    const onRetry = vi.fn();
    render(<CurrentComparison error={new Error("boom")} onRetry={onRetry} />);

    expect(screen.getByText(/No se pudo cargar la comparación/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("marks stale readings with a banner and per-city tag", () => {
    render(
      <CurrentComparison
        data={{
          ...dashboardFixture,
          cities: [{ ...santiago, source: "stale", freshness: "stale" }, valparaiso],
        }}
      />,
    );

    expect(screen.getByText(/Algunas lecturas no están actualizadas/)).toBeInTheDocument();
    expect(screen.getByText("Desactualizado")).toBeInTheDocument();
  });

  it("marks a side without a stored observation as unavailable", () => {
    render(
      <CurrentComparison
        data={{
          ...dashboardFixture,
          cities: [
            santiago,
            {
              ...valparaiso,
              current: null,
              freshness: "unavailable",
              observed_at: null,
              age_seconds: null,
              source: "stale",
            },
          ],
        }}
      />,
    );

    expect(
      screen.getByText(/Aún no hay observaciones almacenadas para esta ciudad/),
    ).toBeInTheDocument();
    expect(screen.getByText("No disponible")).toBeInTheDocument();
  });
});
