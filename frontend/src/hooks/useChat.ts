import { useCallback, useEffect, useState } from "react";

import { api, ApiRequestError } from "../api/client";
import type { ChatMessage } from "../types/chat";

export type ChatRunState = "idle" | "in_progress" | "completed" | "failed";

const SESSION_KEY = "weather-chat-session";

function newSessionId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
    const value = Math.floor(Math.random() * 16);
    const digit = char === "x" ? value : (value & 0x3) | 0x8;
    return digit.toString(16);
  });
}

function readSessionId(): string {
  try {
    const stored = window.localStorage.getItem(SESSION_KEY);
    if (stored) return stored;
  } catch {
    // Storage can be unavailable (private mode); fall back to an in-memory id.
  }
  const created = newSessionId();
  try {
    window.localStorage.setItem(SESSION_KEY, created);
  } catch {
    // Ignore storage failures; the session still works for this page load.
  }
  return created;
}

function persistSessionId(sessionId: string): void {
  try {
    window.localStorage.setItem(SESSION_KEY, sessionId);
  } catch {
    // Ignore storage failures.
  }
}

function historyErrorCopy(error: unknown): string {
  if (error instanceof ApiRequestError && error.code === "invalid_chat") {
    return "No se pudo cargar el historial porque la sesión no es válida.";
  }
  return "No se pudo cargar el historial del chat. Inténtalo de nuevo.";
}

function sendErrorCopy(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.code === "rate_limited") {
      return "Has enviado demasiadas preguntas seguidas. Espera un momento e inténtalo de nuevo.";
    }
    return "No se pudo enviar la pregunta. Inténtalo de nuevo.";
  }
  return "No se pudo contactar con el asistente. Comprueba tu conexión.";
}

export function failureCopy(errorCode: string | null): string {
  switch (errorCode) {
    case "llm_not_configured":
      return "El asistente no está configurado. Falta una clave de LLM en el servidor.";
    case "llm_unavailable":
      return "El asistente no está disponible en este momento. Inténtalo de nuevo más tarde.";
    case "llm_empty_response":
      return "El asistente no devolvió una respuesta. Reformula la pregunta.";
    case "tool_round_limit":
      return "La consulta necesitó demasiados pasos. Intenta ser más específico.";
    default:
      return "El asistente no pudo completar la respuesta.";
  }
}

export function useChat() {
  const [sessionId] = useState<string>(readSessionId);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<ChatRunState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);

  const loadHistory = useCallback(async () => {
    setIsLoadingHistory(true);
    setError(null);
    try {
      const history = await api.loadChatHistory(sessionId);
      setMessages(history.messages);
    } catch (loadError) {
      setError(historyErrorCopy(loadError));
    } finally {
      setIsLoadingHistory(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const sendMessage = useCallback(
    async (raw: string) => {
      const text = raw.trim();
      if (!text || status === "in_progress") return;

      const optimistic: ChatMessage = {
        id: -Date.now(),
        role: "user",
        content: text,
        status: "completed",
        error_code: null,
        created_at: new Date().toISOString(),
        tool_runs: [],
      };
      setMessages((current) => [...current, optimistic]);
      setStatus("in_progress");
      setError(null);
      try {
        const turn = await api.sendChatMessage(sessionId, text);
        persistSessionId(turn.session_id);
        setMessages((current) => [...current, turn.message]);
        setStatus(turn.message.status === "failed" ? "failed" : "completed");
      } catch (sendError) {
        setStatus("failed");
        setError(sendErrorCopy(sendError));
      }
    },
    [sessionId, status],
  );

  return {
    sessionId,
    messages,
    status,
    error,
    isLoadingHistory,
    sendMessage,
    reload: loadHistory,
  };
}
