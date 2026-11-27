import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";

import { chatMessages, chatTurnFor } from "../tests/fixtures";
import { server } from "../tests/mocks/server";
import { ChatPanel } from "./ChatPanel";

const SESSION_KEY = "weather-chat-session";

async function openPanel() {
  const user = userEvent.setup();
  render(<ChatPanel />);
  await user.click(screen.getByRole("button", { name: /Abrir el asistente/ }));
  return user;
}

describe("ChatPanel", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("opens from the FAB and shows an instructive empty state", async () => {
    await openPanel();

    expect(await screen.findByText("Asistente de datos climáticos")).toBeInTheDocument();
    expect(await screen.findByText(/Aún no hay mensajes/)).toBeInTheDocument();
    expect(await screen.findByText("gpt-4o-mini")).toBeInTheDocument();
    expect(screen.getByText("configurado")).toBeInTheDocument();
    expect(screen.getByLabelText("Pregunta sobre el clima")).toBeInTheDocument();
  });

  it("sends a question, shows the assistant answer and the tool used", async () => {
    const user = await openPanel();
    const input = await screen.findByLabelText("Pregunta sobre el clima");

    await user.type(input, "¿Cuál fue la temperatura promedio en Santiago?");
    await user.click(screen.getByRole("button", { name: /Enviar/ }));

    expect(
      await screen.findByText("¿Cuál fue la temperatura promedio en Santiago?"),
    ).toBeInTheDocument();
    expect(
      await screen.findByText(/El promedio fue de 18,6 °C sobre 24 observaciones/),
    ).toBeInTheDocument();
    expect(await screen.findByText("calcular_estadistica")).toBeInTheDocument();
    expect(window.localStorage.getItem(SESSION_KEY)).toBeTruthy();
  });

  it("restores stored history when the panel is reopened", async () => {
    server.use(
      http.get("*/chat/messages/", ({ request }) => {
        const sessionId = new URL(request.url).searchParams.get("session_id") ?? "";
        return HttpResponse.json({ session_id: sessionId, messages: chatMessages });
      }),
    );

    await openPanel();

    expect(await screen.findByText(chatMessages[0].content)).toBeInTheDocument();
    expect(await screen.findByText(chatMessages[1].content)).toBeInTheDocument();
    expect(await screen.findByText("calcular_estadistica")).toBeInTheDocument();
  });

  it("shows a Spanish safe failure when the LLM is not configured", async () => {
    server.use(
      http.post("*/chat/messages/", async ({ request }) => {
        const body = (await request.json()) as { session_id: string };
        const turn = chatTurnFor(body.session_id);
        return HttpResponse.json({
          ...turn,
          message: {
            ...turn.message,
            content: "",
            status: "failed",
            error_code: "llm_not_configured",
          },
        });
      }),
    );

    const user = await openPanel();
    await user.type(await screen.findByLabelText("Pregunta sobre el clima"), "Hola");
    await user.click(screen.getByRole("button", { name: /Enviar/ }));

    expect(
      await screen.findByText(/El asistente no está configurado/),
    ).toBeInTheDocument();
    expect(screen.getByText(/llm_not_configured/)).toBeInTheDocument();
  });

  it("shows a Spanish error when the request fails", async () => {
    server.use(
      http.post("*/chat/messages/", () => new HttpResponse(null, { status: 500 })),
    );

    const user = await openPanel();
    await user.type(await screen.findByLabelText("Pregunta sobre el clima"), "Hola");
    await user.click(screen.getByRole("button", { name: /Enviar/ }));

    expect(
      await screen.findByText(/No se pudo enviar la pregunta/),
    ).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Falló"));
  });
});
