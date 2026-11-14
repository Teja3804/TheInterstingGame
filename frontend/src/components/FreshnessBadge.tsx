import type { Freshness } from "../api";

const LABELS: Record<Freshness, string> = {
  fresh: "Fresh",
  stale: "Stale",
  missing: "No data",
  unknown: "Unknown",
};

const HINTS: Record<Freshness, string> = {
  fresh: "The latest stored candle is the last completed session.",
  stale: "A newer session has completed since the latest stored candle. Refresh the data.",
  missing: "Nothing is stored for this symbol yet.",
  unknown: "The market calendar could not name a last completed session.",
};

export function FreshnessBadge({ state }: { state: Freshness }) {
  return (
    <span className={`badge badge-${state}`} title={HINTS[state]}>
      {LABELS[state]}
    </span>
  );
}
