import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { observationsFixture } from "../tests/fixtures";
import { ObservationsTable } from "./ObservationsTable";

describe("ObservationsTable", () => {
  it("renders server-paginated rows and requests the next page", async () => {
    const onPageChange = vi.fn();
    const user = userEvent.setup();
    render(
      <ObservationsTable
        data={{ ...observationsFixture, count: 40, total_pages: 2 }}
        page={1}
        pageSize={20}
        onPageChange={onPageChange}
      />,
    );

    expect(screen.getAllByText("Santiago").length).toBeGreaterThan(0);
    expect(screen.getByText("40 observaciones · página 1 de 2")).toBeInTheDocument();

    await user.click(screen.getByTitle("Next Page"));
    expect(onPageChange).toHaveBeenCalledWith(2, 20);
  });

  it("shows an empty state for an out-of-range page", () => {
    render(
      <ObservationsTable
        data={{
          ...observationsFixture,
          count: 0,
          total_pages: 0,
          results: [],
        }}
        page={9}
        pageSize={20}
        city="Santiago"
        onPageChange={vi.fn()}
      />,
    );

    expect(
      screen.getByText(/No hay observaciones que coincidan con “Santiago”/),
    ).toBeInTheDocument();
  });

  it("changes the page size through the pagination control", async () => {
    const onPageChange = vi.fn();
    const user = userEvent.setup();
    render(
      <ObservationsTable
        data={observationsFixture}
        page={1}
        pageSize={20}
        onPageChange={onPageChange}
      />,
    );

    await user.click(screen.getByText("20 / page"));
    await user.click(await screen.findByText("50 / page"));
    await waitFor(() => expect(onPageChange).toHaveBeenCalledWith(1, 50));
  });

  it("shows an error state with a retry button", async () => {
    const onRetry = vi.fn();
    render(
      <ObservationsTable
        error={new Error("db down")}
        page={1}
        pageSize={20}
        onPageChange={vi.fn()}
        onRetry={onRetry}
      />,
    );

    expect(screen.getByText(/No se pudo cargar la tabla de observaciones/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
