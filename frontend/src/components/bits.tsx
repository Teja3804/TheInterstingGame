import type { ReactNode } from "react";
import { formatNumber } from "../format";

const ACTION_CLASS: Record<string, string> = {
  "Buy candidate": "chip-buy",
  Watch: "chip-watch",
  "No trade": "chip-none",
  Rejected: "chip-reject",
  Unavailable: "chip-unavailable",
  Hold: "chip-buy",
  Exit: "chip-reject",
  "Hold, consider hedging or reducing": "chip-warn",
};

export function ActionChip({ action, large = false }: { action: string; large?: boolean }) {
  return (
    <span className={`chip ${ACTION_CLASS[action] ?? "chip-none"}${large ? " chip-large" : ""}`}>
      {action}
    </span>
  );
}

/** A 0 to 100 score as a number with a bar. The bar is decoration; the number is the value. */
export function ScoreMeter({ score, compact = false }: { score: number | null; compact?: boolean }) {
  if (score === null) return <span className="muted">–</span>;
  return (
    <span className={compact ? "meter meter-compact" : "meter"}>
      <span className="meter-value">{formatNumber(score, 0)}</span>
      <span className="meter-track" aria-hidden="true">
        <span className="meter-fill" style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
      </span>
    </span>
  );
}

/** Tiny line of recent closes. Shape only: no axis, no values. */
export function Spark({ values }: { values: (number | null)[] | undefined }) {
  const points = (values ?? []).filter((v): v is number => v !== null);
  if (points.length < 2) return null;
  const low = Math.min(...points);
  const span = Math.max(...points) - low || 1;
  const path = points
    .map((v, i) => `${(i / (points.length - 1)) * 100},${28 - ((v - low) / span) * 26}`)
    .join(" ");
  const rising = points[points.length - 1] >= points[0];
  return (
    <svg className={rising ? "spark up" : "spark down"} viewBox="0 0 100 30" aria-hidden="true">
      <polyline points={path} fill="none" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

export function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "up" | "down";
}) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${tone ?? ""}`}>{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}

export function Section({
  title,
  aside,
  children,
}: {
  title: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

export function BacktestTag() {
  return (
    <span className="tag tag-backtest" title="What the rules would have done on past data">
      BACKTEST
    </span>
  );
}

export function Warnings({ items }: { items: string[] }) {
  return (
    <details className="warnings">
      <summary>How to read these numbers ({items.length} cautions)</summary>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </details>
  );
}

export const r = (value: number | null | undefined, digits = 2) =>
  value === null || value === undefined
    ? "–"
    : `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value).toFixed(digits)} R`;

export const pct = (fraction: number | null | undefined, digits = 0) =>
  fraction === null || fraction === undefined ? "–" : `${(fraction * 100).toFixed(digits)}%`;

export const signed = (value: number | null | undefined, digits = 1) =>
  value === null || value === undefined
    ? "–"
    : `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value).toFixed(digits)}%`;
