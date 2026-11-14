// Display formatting only. Nothing here computes a financial value.

const DASH = "–";
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** A fraction such as 0.0123 shown as "+1.23%". */
export function formatFraction(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return formatPercent(value * 100, digits);
}

/** A value already in percent such as 1.23 shown as "+1.23%". */
export function formatPercent(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(digits)}%`;
}

export function signClass(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value) || value === 0) return "";
  return value > 0 ? "up" : "down";
}

/** "2024-03-08" -> "8 Mar 2024". The string is not passed through Date, so no zone shift. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) return iso;
  return `${Number(match[3])} ${MONTHS[Number(match[2]) - 1]} ${match[1]}`;
}

/**
 * The backend sends market-local times with their offset, e.g. "2024-03-08T16:00:00-05:00".
 * Show the wall-clock part as written and name the zone: "8 Mar 2024, 16:00 America/New_York".
 */
export function formatLocal(iso: string | null | undefined, zone: string): string {
  if (!iso) return DASH;
  const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(iso);
  if (!match) return iso;
  return `${formatDate(match[1])}, ${match[2]} ${zone}`;
}

export function localClock(iso: string): string {
  const match = /T(\d{2}:\d{2})/.exec(iso);
  return match ? match[1] : DASH;
}

/** A stored UTC instant shown in a market's zone, with the zone named. */
export function formatInstant(utcIso: string | null | undefined, zone: string): string {
  if (!utcIso) return DASH;
  const date = new Date(utcIso);
  if (Number.isNaN(date.getTime())) return utcIso;
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: zone,
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
  return `${parts} ${zone}`;
}

export function formatVolume(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return value.toLocaleString("en-US", { notation: "compact", maximumFractionDigits: 2 });
}
