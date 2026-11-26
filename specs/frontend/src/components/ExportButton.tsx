import { useState } from "react";
import { Alert, Button } from "antd";
import { DownloadOutlined } from "@ant-design/icons";

import { api } from "../api/client";
import type { Window } from "../types/weather";

export interface ExportButtonProps {
  city?: string;
  window: Window;
}

function triggerDownload(content: string, filename: string): void {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function ExportButton({ city, window }: ExportButtonProps) {
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleExport = async () => {
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.exportCsv({ city, window });
      triggerDownload(result.content, result.filename);
      if (result.empty) {
        setNotice("La exportación está vacía: ninguna observación coincide con el filtro actual.");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "La exportación falló.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Button icon={<DownloadOutlined />} loading={loading} onClick={handleExport}>
        Exportar CSV
      </Button>
      {notice ? (
        <Alert type="info" showIcon style={{ marginTop: 8 }} message={notice} role="status" />
      ) : null}
      {error ? (
        <Alert type="error" showIcon style={{ marginTop: 8 }} message={error} role="alert" />
      ) : null}
    </div>
  );
}
