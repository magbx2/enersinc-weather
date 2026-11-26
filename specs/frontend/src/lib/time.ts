const MS_PER_MINUTE = 60_000;
const MS_PER_HOUR = 3_600_000;
const MS_PER_DAY = 86_400_000;

export function formatTimestamp(iso: string | null, locale?: string): string {
  if (!iso) return "Sin observación";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Hora no válida";
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(date);
}

export function formatAge(ageSeconds: number | null): string {
  if (ageSeconds === null) return "no disponible";
  if (ageSeconds < 60) return `hace ${Math.max(0, Math.round(ageSeconds))}s`;
  const minutes = Math.round(ageSeconds / 60);
  if (minutes < 60) return `hace ${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `hace ${hours}h`;
  return `hace ${Math.round(hours / 24)}d`;
}

export function relativeAge(iso: string | null, now: Date = new Date()): string {
  if (!iso) return "no disponible";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "no disponible";
  return formatAge(Math.max(0, (now.getTime() - date.getTime()) / 1000));
}

export function isStale(
  observedAt: string | null,
  now: Date = new Date(),
  windowMs = MS_PER_MINUTE,
): boolean {
  if (!observedAt) return true;
  const date = new Date(observedAt);
  if (Number.isNaN(date.getTime())) return true;
  return now.getTime() - date.getTime() > windowMs;
}

export function signed(value: number | null, digits = 1): string {
  if (value === null) return "—";
  const rounded = Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(digits);
  return value > 0 ? `+${rounded}` : rounded;
}

export { MS_PER_DAY, MS_PER_HOUR, MS_PER_MINUTE };
