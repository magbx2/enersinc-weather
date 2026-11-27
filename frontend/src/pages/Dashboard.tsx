import { useCallback, useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { Button, Divider, Layout, Select, Space, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";

import { CitySelector } from "../components/CitySelector";
import { ChatPanel } from "../components/ChatPanel";
import { ConnectionBadge } from "../components/ConnectionBadge";
import { CurrentComparison } from "../components/CurrentComparison";
import { ExportButton } from "../components/ExportButton";
import { HistoryCharts } from "../components/HistoryCharts";
import { ObservationsTable } from "../components/ObservationsTable";
import { useDashboardData } from "../hooks/useDashboardData";
import { useObservations } from "../hooks/useObservations";
import type { Window } from "../types/weather";

const WINDOWS: Window[] = ["24h", "7d", "30d"];

function parseWindow(value: string | null): Window {
  return WINDOWS.includes(value as Window) ? (value as Window) : "24h";
}

function positiveInt(value: string | null, fallback: number, max: number): number {
  const parsed = Number.parseInt(value ?? "", 10);
  if (!Number.isFinite(parsed) || parsed < 1) return fallback;
  return Math.min(parsed, max);
}

export function Dashboard() {
  const [params, setParams] = useSearchParams();

  const cityA = params.get("city_a") ?? "";
  const cityB = params.get("city_b") ?? "";
  const window = parseWindow(params.get("window"));
  const page = positiveInt(params.get("page"), 1, 10_000);
  const pageSize = positiveInt(params.get("page_size"), 20, 100);
  const cityFilter = params.get("city") ?? "";

  const update = useCallback(
    (changes: Record<string, string | null>, resetPage = false) => {
      setParams(
        (current) => {
          const next = new URLSearchParams(current);
          for (const [key, value] of Object.entries(changes)) {
            if (value === null || value === "") next.delete(key);
            else next.set(key, value);
          }
          if (resetPage) next.set("page", "1");
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  const { query, refresh, socketStatus } = useDashboardData(cityA || null, cityB || null, window);
  const observations = useObservations({ page, pageSize, city: cityFilter || undefined });

  // On "/" the backend returns the stored default pair. Reflect it in the URL
  // so the selectors, live subscription and table share the same state.
  useEffect(() => {
    if (cityA || cityB || !query.data) return;
    const [first, second] = query.data.cities;
    if (!first || !second) return;
    update({ city_a: first.city, city_b: second.city });
  }, [cityA, cityB, query.data, update]);

  const chartCities = useMemo(() => {
    if (!query.data) return undefined;
    if (!cityFilter) return query.data.cities;
    return query.data.cities.filter((city) => city.city === cityFilter);
  }, [query.data, cityFilter]);

  const cityOptions = useMemo(() => {
    const values = [cityA, cityB].filter(Boolean);
    return [
      { label: "Ambas ciudades", value: "" },
      ...values.map((city) => ({ label: city, value: city })),
    ];
  }, [cityA, cityB]);

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Layout.Content style={{ width: "100%", maxWidth: 1200, margin: "0 auto", padding: 16 }}>
        <Space
          style={{ width: "100%", justifyContent: "space-between", flexWrap: "wrap", rowGap: 8 }}
          align="center"
        >
          <Typography.Title level={2} style={{ margin: 0 }}>
            Comparación del tiempo entre dos ciudades
          </Typography.Title>
          <ConnectionBadge status={socketStatus} />
        </Space>

        <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
          Todas las horas se muestran en tu zona horaria local. Los valores provienen únicamente de
          observaciones almacenadas.
        </Typography.Paragraph>

        <Space style={{ width: "100%", flexWrap: "wrap" }} size="middle" align="end">
          <div style={{ minWidth: 240, flex: 1 }}>
            <CitySelector
              label="Primera ciudad"
              value={cityA}
              otherValue={cityB}
              onSelect={(city) => update({ city_a: city }, true)}
            />
          </div>
          <div style={{ minWidth: 240, flex: 1 }}>
            <CitySelector
              label="Segunda ciudad"
              value={cityB}
              otherValue={cityA}
              onSelect={(city) => update({ city_b: city }, true)}
            />
          </div>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => refresh.mutate()}
            loading={refresh.isPending}
            disabled={!cityA || !cityB}
          >
            Actualizar ahora
          </Button>
        </Space>

        <Divider />

        <CurrentComparison
          data={query.data}
          isLoading={query.isLoading}
          error={query.error}
          onRetry={() => void query.refetch()}
        />

        <Divider />

        <Space
          style={{ width: "100%", justifyContent: "space-between", flexWrap: "wrap", rowGap: 8 }}
          align="center"
        >
          <Select
            aria-label="Filtrar la tabla por ciudad"
            value={cityFilter}
            options={cityOptions}
            style={{ minWidth: 200 }}
            onChange={(value) => update({ city: value || null }, true)}
            disabled={!cityA || !cityB}
          />
          <ExportButton city={cityFilter || undefined} window={window} />
        </Space>

        <div style={{ marginTop: 16 }}>
          <HistoryCharts
            cities={chartCities}
            window={window}
            onWindowChange={(next) => update({ window: next }, true)}
            isLoading={query.isLoading}
            error={query.error}
            onRetry={() => void query.refetch()}
          />
        </div>

        <div style={{ marginTop: 16 }}>
          <ObservationsTable
            data={observations.data}
            isLoading={observations.isLoading}
            error={observations.error}
            onRetry={() => void observations.refetch()}
            page={page}
            pageSize={pageSize}
            city={cityFilter || undefined}
            onPageChange={(nextPage, nextPageSize) =>
              update({ page: String(nextPage), page_size: String(nextPageSize) })
            }
          />
        </div>
      </Layout.Content>
      <ChatPanel />
    </Layout>
  );
}
