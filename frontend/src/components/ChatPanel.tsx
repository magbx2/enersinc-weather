import { useEffect, useRef, useState } from "react";
import { Alert, Button, Drawer, Input, Space, Spin, Tag, Typography } from "antd";
import { CommentOutlined, SendOutlined } from "@ant-design/icons";

import { api } from "../api/client";
import { failureCopy, useChat, type ChatRunState } from "../hooks/useChat";
import type { Health } from "../types/weather";

function statusTag(status: ChatRunState) {
  switch (status) {
    case "in_progress":
      return (
        <Tag color="processing" icon={<Spin size="small" />}>
          Procesando…
        </Tag>
      );
    case "completed":
      return <Tag color="success">Completado</Tag>;
    case "failed":
      return <Tag color="error">Falló</Tag>;
    default:
      return <Tag>Listo</Tag>;
  }
}

export function ChatPanel() {
  const { messages, status, error, isLoadingHistory, sendMessage, reload } = useChat();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [llm, setLlm] = useState<Health["llm"] | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open || llm) return;
    let cancelled = false;
    api
      .health()
      .then((health) => {
        if (!cancelled) setLlm(health.llm ?? null);
      })
      .catch(() => {
        // The run status and error states already explain connectivity failures.
      });
    return () => {
      cancelled = true;
    };
  }, [open, llm]);

  useEffect(() => {
    if (!open) return;
    const node = listRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages, status, open]);

  const submit = () => {
    const text = draft.trim();
    if (!text || status === "in_progress") return;
    setDraft("");
    void sendMessage(text);
  };

  return (
    <>
      <Button
        type="primary"
        shape="circle"
        size="large"
        aria-label="Abrir el asistente de datos climáticos"
        icon={<CommentOutlined />}
        onClick={() => setOpen(true)}
        style={{ position: "fixed", right: 24, bottom: 24, zIndex: 1000, width: 56, height: 56 }}
      />
      <Drawer
        title="Asistente de datos climáticos"
        placement="right"
        width="min(440px, 100vw)"
        open={open}
        onClose={() => setOpen(false)}
        styles={{
          body: { display: "flex", flexDirection: "column", gap: 12, padding: 12, minHeight: 0 },
        }}
      >
        <div
          role="status"
          aria-live="polite"
          style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}
        >
          <Typography.Text type="secondary">Estado del run:</Typography.Text>
          {statusTag(status)}
          {llm && (
            <>
              <Typography.Text type="secondary">Modelo:</Typography.Text>
              <Tag color={llm.configured ? "green" : "orange"}>
                {llm.configured ? "configurado" : "no configurado"}
              </Tag>
              <Typography.Text code>{llm.model ?? "modelo por defecto"}</Typography.Text>
            </>
          )}
        </div>

        <div
          ref={listRef}
          data-testid="chat-history"
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: 10,
            paddingRight: 4,
          }}
        >
          {isLoadingHistory ? (
            <div style={{ textAlign: "center", padding: 24 }}>
              <Spin />
              <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
                Cargando historial…
              </Typography.Paragraph>
            </div>
          ) : messages.length === 0 ? (
            <Typography.Paragraph type="secondary" style={{ marginTop: 12 }}>
              Aún no hay mensajes. Pregunta por la temperatura, la humedad o el viento de una ciudad
              y su rango de fechas.
            </Typography.Paragraph>
          ) : (
            messages.map((message) => {
              const isUser = message.role === "user";
              return (
                <div
                  key={`${message.id}-${message.created_at}`}
                  style={{
                    alignSelf: isUser ? "flex-end" : "flex-start",
                    maxWidth: "92%",
                    display: "flex",
                    flexDirection: "column",
                    gap: 6,
                  }}
                >
                  <div
                    style={{
                      background: isUser ? "#e6f4ff" : "#f5f5f5",
                      border: "1px solid #e5e5e5",
                      borderRadius: 10,
                      padding: "8px 10px",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                    }}
                  >
                    {message.content || (message.status === "failed" ? "Sin respuesta." : "…")}
                  </div>
                  {message.role === "assistant" && message.tool_runs.length > 0 && (
                    <Space size={[4, 4]} wrap aria-label="Herramientas utilizadas">
                      <Typography.Text type="secondary">Herramientas:</Typography.Text>
                      {message.tool_runs.map((run, index) => (
                        <Tag
                          key={`${run.name}-${index}`}
                          color={run.status === "ok" ? "blue" : "red"}
                          title={`Argumentos saneados: ${JSON.stringify(run.arguments)}`}
                        >
                          {run.name}
                        </Tag>
                      ))}
                    </Space>
                  )}
                  {message.role === "assistant" && message.status === "failed" && (
                    <Alert
                      type="warning"
                      showIcon
                      message={failureCopy(message.error_code)}
                      description={
                        message.error_code ? `Código técnico: ${message.error_code}` : undefined
                      }
                    />
                  )}
                </div>
              );
            })
          )}
        </div>

        {error && (
          <Alert
            type="error"
            showIcon
            message={error}
            action={
              <Button size="small" onClick={() => void reload()}>
                Reintentar
              </Button>
            }
          />
        )}

        <Space.Compact style={{ width: "100%" }}>
          <Input.TextArea
            aria-label="Pregunta sobre el clima"
            placeholder="P. ej., ¿Cuál fue la temperatura promedio en Santiago en los últimos 7 días?"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onPressEnter={(event) => {
              if (!event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            autoSize={{ minRows: 1, maxRows: 4 }}
            maxLength={2000}
            disabled={status === "in_progress"}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={submit}
            loading={status === "in_progress"}
            disabled={!draft.trim() || status === "in_progress"}
          >
            Enviar
          </Button>
        </Space.Compact>
      </Drawer>
    </>
  );
}
