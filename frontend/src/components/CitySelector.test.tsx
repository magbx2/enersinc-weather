import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CitySelector } from "./CitySelector";

describe("CitySelector", () => {
  it("searches after the debounce and selects a city", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<CitySelector label="First city" value="" onSelect={onSelect} />);

    await user.type(screen.getByRole("combobox", { name: "First city" }), "San");
    const option = await screen.findByText(/Santiago, Region Metropolitana/, {}, { timeout: 2500 });
    await user.click(option);

    await waitFor(() => expect(onSelect).toHaveBeenCalledWith("Santiago"));
  });

  it("rejects selecting the same city twice", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<CitySelector label="Second city" value="" otherValue="Santiago" onSelect={onSelect} />);

    await user.type(screen.getByRole("combobox", { name: "Second city" }), "San");
    const option = await screen.findByText(/Santiago, Region Metropolitana/, {}, { timeout: 2500 });
    await user.click(option);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Las dos ciudades deben ser diferentes.",
    );
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("explains an unknown city without inventing a value", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<CitySelector label="First city" value="" onSelect={onSelect} />);

    await user.type(screen.getByRole("combobox", { name: "First city" }), "Nowhere");
    expect(await screen.findByRole("alert", {}, { timeout: 2500 })).toHaveTextContent(
      "Ninguna ciudad coincide con “Nowhere”.",
    );
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("does not search for an empty query", async () => {
    const user = userEvent.setup();
    render(<CitySelector label="First city" value="" onSelect={vi.fn()} />);

    await user.type(screen.getByRole("combobox", { name: "First city" }), "   ");
    await new Promise((resolve) => setTimeout(resolve, 400));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
