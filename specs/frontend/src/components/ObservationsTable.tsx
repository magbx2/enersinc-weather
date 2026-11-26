import { Alert, Button, Empty, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { Observation, PaginatedObservations } from "../types/weather";
import { formatTimestamp } from "../lib/time";

export interface ObservationsTableProps {
  data?: PaginatedObservations;
  isLoading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
  page: number;
  pageSize: number;
  city?: string;
  onPageChange: (page: number, pageSize: number) => void;
}

const columns: ColumnsType<Observation> = [
  {
    title: "Observado (hora local)",
    dataIndex: "timestamp",
    key: "timestamp",
    render: (value: string) => formatTimestamp(value),
  },
  { title: "Ciudad", dataIndex: "city", key: "city" },
  {
    title: "País",
    dataIndex: "country_code",
    key: "country_code",
    render: (value: string | null) => value ?? "—",
  },
  {
    title: "Temperatura (°C)",
    dataIndex: "temperature",
    key: "temperature",
    render: (value: number) => value.toFixed(2),
  },
  { title: "Humedad (%)", dataIndex: "humidity", key: "humidity" },
  {
    title: "Viento (m/s)",
    dataIndex: "wind_speed",
    key: "wind_speed",
    render: (value: number) => value.toFixed(2),
  },
];

export function ObservationsTable({
  data,
  isLoading,
  error,
  onRetry,
  page,
  pageSize,
  city,
  onPageChange,
}: ObservationsTableProps) {
  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        message="No se pudo cargar la tabla de observaciones."
        description={error.message}
        action={
          onRetry ? (
            <Button size="small" onClick={onRetry}>
              Reintentar
            </Button>
          ) : undefined
        }
      />
    );
  }

  const emptyText = city
    ? `No hay observaciones que coincidan con “${city}” en la ventana seleccionada.`
    : "Aún no hay observaciones almacenadas. La primera actualización creará el historial.";

  return (
    <div style={{ overflowX: "auto" }} aria-label="Historial de observaciones">
      <Table<Observation>
        rowKey="id"
        size="small"
        columns={columns}
        dataSource={data?.results ?? []}
        loading={isLoading}
        locale={{ emptyText: <Empty description={emptyText} /> }}
        pagination={{
          current: page,
          pageSize,
          total: data?.count ?? 0,
          showSizeChanger: true,
          pageSizeOptions: [10, 20, 50, 100],
          showTotal: (total) => (
            <Typography.Text>
              {total} {total === 1 ? "observación" : "observaciones"} · página {page} de{" "}
              {Math.max(1, data?.total_pages ?? 1)}
            </Typography.Text>
          ),
          onChange: (nextPage, nextPageSize) => {
            if (nextPageSize !== pageSize) {
              onPageChange(1, nextPageSize);
              return;
            }
            onPageChange(nextPage, nextPageSize);
          },
        }}
      />
    </div>
  );
}
