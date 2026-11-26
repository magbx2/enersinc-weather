import { useMemo } from "react";
import { Alert, Button, Card, Empty, Segmented, Skeleton, Typography } from "antd";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { CitySnapshot, Window } from "../types/weather";
import { formatTimestamp } from "../lib/time";

const COLORS = ["#1677ff", "#fa8c16", "#52c41a", "#eb2f96"];

export interface HistoryChartsProps {
  cities?: CitySnapshot[];
  window: Window;
  onWindowChange: (window: Window) => void;
  isLoading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
}

interface MergedPoint {
  bucket: string;
  [key: string]: string | number | undefined;
}

function mergeSeries(cities: CitySnapshot[]): MergedPoint[] {
  const points = new Map<string, MergedPoint>();
  cities.forEach((city, index) => {
    for (const point of city.series) {
      const existing = points.get(point.bucket_start) ?? { bucket: point.bucket_start };
      points.set(point.bucket_start, {
        ...existing,
        [`${index}_temperature`]: point.temperature,
        [`${index}_humidity`]: point.humidity,
      });
    }
  });
  return [...points.values()].sort((left, right) => left.bucket.localeCompare(right.bucket));
}

function axisLabel(value: string): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit" });
}

export function HistoryCharts({
  cities,
  window,
  onWindowChange,
  isLoading,
  error,
  onRetry,
}: HistoryChartsProps) {
  const merged = useMemo(() => (cities?.length ? mergeSeries(cities) : []), [cities]);

  if (isLoading && !cities) {
    return (
      <div aria-label="Cargando gráficos del historial" role="status">
        <Skeleton active paragraph={{ rows: 8 }} />
      </div>
    );
  }

  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        message="No se pudieron cargar los gráficos del historial."
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

  const toolbar = (
    <Segmented<Window>
      aria-label="Ventana del historial"
      value={window}
      onChange={onWindowChange}
      options={[
        { label: "24 horas", value: "24h" },
        { label: "7 días", value: "7d" },
        { label: "30 días", value: "30d" },
      ]}
    />
  );

  if (!cities || cities.length === 0) {
    return (
      <Card title="Historial" extra={toolbar}>
        <Empty description="Elige dos ciudades para explorar su historial." />
      </Card>
    );
  }

  if (merged.length === 0) {
    return (
      <Card title="Historial" extra={toolbar}>
        <Empty description="Aún no hay historial almacenado para estas ciudades." />
      </Card>
    );
  }

  return (
    <Card title="Historial" extra={toolbar}>
      <ul
        aria-label="Series del gráfico"
        style={{ display: "flex", gap: 24, listStyle: "none", padding: 0, flexWrap: "wrap" }}
      >
        {cities.map((city) => (
          <li key={city.city_key}>
            <Typography.Text strong>{city.city}</Typography.Text> · {city.series.length} intervalos
          </li>
        ))}
      </ul>
      <Typography.Title level={5}>Temperatura (°C)</Typography.Title>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={merged} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="bucket" tickFormatter={axisLabel} minTickGap={24} />
          <YAxis width={48} />
          <Tooltip labelFormatter={(value: string) => formatTimestamp(value)} />
          <Legend />
          {cities.map((city, index) => (
            <Line
              key={city.city_key}
              type="monotone"
              dataKey={`${index}_temperature`}
              name={`${city.city} temperatura`}
              stroke={COLORS[index % COLORS.length]}
              dot={false}
              connectNulls={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <Typography.Title level={5}>Humedad (%)</Typography.Title>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={merged} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="bucket" tickFormatter={axisLabel} minTickGap={24} />
          <YAxis width={48} domain={[0, 100]} />
          <Tooltip labelFormatter={(value: string) => formatTimestamp(value)} />
          <Legend />
          {cities.map((city, index) => (
            <Line
              key={city.city_key}
              type="monotone"
              dataKey={`${index}_humidity`}
              name={`${city.city} humedad`}
              stroke={COLORS[(index + 2) % COLORS.length]}
              dot={false}
              connectNulls={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}
