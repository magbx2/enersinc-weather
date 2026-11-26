import { Alert, Button, Card, Col, Empty, Row, Skeleton, Statistic, Tag, Typography } from "antd";

import type { CitySnapshot, DashboardData } from "../types/weather";
import { formatAge, formatTimestamp, signed } from "../lib/time";

export interface CurrentComparisonProps {
  data?: DashboardData;
  isLoading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
}

function freshnessTag(city: CitySnapshot) {
  if (city.freshness === "unavailable") return <Tag color="default">No disponible</Tag>;
  if (city.freshness === "stale") return <Tag color="orange">Desactualizado</Tag>;
  return city.source === "live" ? <Tag color="green">En vivo</Tag> : <Tag color="blue">Actual</Tag>;
}

function CityPanel({ city }: { city: CitySnapshot }) {
  return (
    <Card
      title={
        <span>
          {city.city} {freshnessTag(city)}
        </span>
      }
      style={{ height: "100%" }}
    >
      {city.current ? (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={24} sm={8}>
              <Statistic
                title="Temperatura"
                value={city.current.temperature}
                precision={1}
                suffix="°C"
              />
            </Col>
            <Col xs={24} sm={8}>
              <Statistic title="Humedad" value={city.current.humidity} suffix="%" />
            </Col>
            <Col xs={24} sm={8}>
              <Statistic
                title="Velocidad del viento"
                value={city.current.wind_speed}
                precision={1}
                suffix="m/s"
              />
            </Col>
          </Row>
          <Typography.Paragraph style={{ marginTop: 16, marginBottom: 0 }}>
            Medido {formatTimestamp(city.observed_at)} ({formatAge(city.age_seconds)})
          </Typography.Paragraph>
        </>
      ) : (
        <Alert
          type="warning"
          showIcon
          message="Aún no hay observaciones almacenadas para esta ciudad."
          description={
            city.reason
              ? `La fuente en vivo no está disponible (${city.reason}).`
              : "Los valores aparecerán tras la próxima actualización correcta."
          }
        />
      )}
    </Card>
  );
}

export function CurrentComparison({ data, isLoading, error, onRetry }: CurrentComparisonProps) {
  if (isLoading && !data) {
    return (
      <div aria-label="Cargando comparación" role="status">
        <Skeleton active paragraph={{ rows: 6 }} />
      </div>
    );
  }

  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        message="No se pudo cargar la comparación."
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

  if (!data || data.cities.length !== 2) {
    return <Empty description="Elige dos ciudades para comparar su tiempo." />;
  }

  const [first, second] = data.cities;
  const stale = data.cities.some((city) => city.freshness !== "current");

  return (
    <section aria-label="Comparación actual">
      {stale ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="Algunas lecturas no están actualizadas"
          description="La fuente en vivo no está disponible, por lo que se muestran observaciones almacenadas marcadas como desactualizadas."
        />
      ) : null}
      <Row gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <CityPanel city={first} />
        </Col>
        <Col xs={24} md={12}>
          <CityPanel city={second} />
        </Col>
      </Row>
      <Card
        size="small"
        title={`Diferencia (${first.city} − ${second.city})`}
        style={{ marginTop: 16 }}
      >
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={8}>
            <Statistic
              title="Diferencia de temperatura"
              value={signed(data.comparison.temperature_delta)}
              suffix="°C"
            />
          </Col>
          <Col xs={24} sm={8}>
            <Statistic
              title="Diferencia de humedad"
              value={signed(data.comparison.humidity_delta, 0)}
              suffix="pp"
            />
          </Col>
          <Col xs={24} sm={8}>
            <Statistic
              title="Diferencia de viento"
              value={signed(data.comparison.wind_speed_delta)}
              suffix="m/s"
            />
          </Col>
        </Row>
        {data.comparison.warmer_city ? (
          <Typography.Paragraph style={{ marginTop: 12, marginBottom: 0 }}>
            Ciudad más cálida: <strong>{data.comparison.warmer_city}</strong>
          </Typography.Paragraph>
        ) : null}
      </Card>
    </section>
  );
}
