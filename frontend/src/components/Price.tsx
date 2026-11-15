import type { Provenance } from "../api";
import { formatDate, formatLocal, formatNumber } from "../format";
import { FreshnessBadge } from "./FreshnessBadge";

/** A price is never shown without its currency, as-of time (market zone) and freshness. */
export function Price({
  value,
  from,
  size = "normal",
}: {
  value: number | null | undefined;
  from: Provenance;
  size?: "normal" | "large";
}) {
  const asOf = from.as_of_local
    ? formatLocal(from.as_of_local, from.timezone)
    : from.candle_date
      ? `${formatDate(from.candle_date)} (${from.timezone})`
      : null;
  return (
    <span className={`price price-${size}`}>
      <span className="price-value">
        {formatNumber(value)} <span className="currency">{from.currency}</span>
      </span>
      <span className="price-meta">
        {asOf ? `Close as of ${asOf}` : "Unavailable: no data stored"}
        <FreshnessBadge state={from.freshness} />
      </span>
    </span>
  );
}
