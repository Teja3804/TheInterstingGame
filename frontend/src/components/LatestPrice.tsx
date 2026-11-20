import type { Quote } from "../api";
import { formatLocal, formatNumber, formatPercent, signClass } from "../format";

/** "Delayed price at 12:45" during a session, "Close, 8 Mar 2024 16:00" after it. */
export function quoteTimeLabel(quote: Quote, zone: string): string {
  const when = formatLocal(quote.market_time_local, zone);
  return quote.kind === "during_session" ? `Delayed price, ${when}` : `Closing price, ${when}`;
}

function changeLabel(quote: Quote): string {
  return quote.kind === "during_session" ? "today" : "on the day";
}

/**
 * The latest delayed price from the provider, with its currency, its own time in the market
 * zone, and the change versus the previous close as the backend computed it.
 */
export function LatestPrice({
  quote,
  zone,
  size = "normal",
}: {
  quote: Quote | undefined;
  zone: string;
  size?: "normal" | "large";
}) {
  if (!quote || quote.price === null) {
    return (
      <span className={`price price-${size}`}>
        <span className="price-meta">
          Latest price unavailable: {quote?.unavailable_reason ?? "no quote published yet"}
        </span>
      </span>
    );
  }
  const warnings = quote.warnings ?? [];
  return (
    <span className={`price price-${size}`}>
      <span className="price-value">
        {formatNumber(quote.price)} <span className="currency">{quote.currency}</span>
      </span>
      <span className="price-meta">
        <span className={signClass(quote.change_pct)}>
          {formatPercent(quote.change_pct)} {changeLabel(quote)}
        </span>
        <span>{quoteTimeLabel(quote, zone)}</span>
      </span>
      {warnings.length > 0 && (
        <span className="price-warning" title={warnings.join("\n")}>
          Check: {warnings.map((w) => w.split(":")[0].replace(/_/g, " ")).join(", ")}
        </span>
      )}
      {quote.last_error && (
        <span className="price-warning" title={quote.last_error}>
          Last refresh failed; showing the previous quote
        </span>
      )}
    </span>
  );
}
