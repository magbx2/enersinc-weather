import { Tag } from "antd";

import type { SocketStatus } from "../types/weather";

const LABELS: Record<SocketStatus, { text: string; color: string }> = {
  connecting: { text: "Conectando a las actualizaciones en vivo", color: "processing" },
  live: { text: "Actualizaciones en vivo activas", color: "success" },
  reconnecting: { text: "Reconectando a las actualizaciones en vivo", color: "warning" },
  paused: { text: "Actualizaciones en vivo en pausa", color: "default" },
};

export function ConnectionBadge({ status }: { status: SocketStatus }) {
  const label = LABELS[status];
  return (
    <div role="status" aria-live="polite" aria-atomic="true">
      <Tag color={label.color}>{label.text}</Tag>
    </div>
  );
}
