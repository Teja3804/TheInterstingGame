import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type WatchMarket, type WatchRow } from "../api";
import { FreshnessBadge } from "../components/FreshnessBadge";
import {
  formatDate,
  formatFraction,
  formatLocal,
  formatNumber,
  formatPercent,
  signClass,
} from "../format";
import { useLoad } from "../useLoad";

function Cell({
  row,
  field,
  kind,
}: {
  row: WatchRow;
  field: string;
  kind: "fraction" | "percent" | "number";
}) {
  const value = row.values[field];
  const reason = row.unavailable[field] ?? row.unavailable_reason;
  if (value === null || value === undefined) {
    return (
      <td className="num muted" title={reason ?? "unavailable"}>
        –
      </td>
    );
  }
  if (kind === "number") return <td className="num">{formatNumber(value)}</td>;
  const text = kind === "fraction" ? formatFraction(value) : formatPercent(value);
  return <td className={`num ${signClass(value)}`}>{text}</td>;
}

function MarketTable({ market }: { market: WatchMarket }) {
  return (
    <div className="table-scroll">
      <table className="watch">
        <thead>
          <tr>
            <th>Symbol</th>
            <th className="num">Last close ({market.currency})</th>
            <th>As of ({market.timezone})</th>
            <th>Freshness</th>
            <th className="num">1 session</th>
            <th className="num">5 sessions</th>
            <th className="num">20 sessions</th>
            <th className="num">RSI 14</th>
            <th className="num">vs SMA 50</th>
            <th className="num">vs SMA 200</th>
            <th className="num">Rel. volume</th>
            <th className="num">ATR %</th>
            <th className="num" title={`Return minus ${market.relative_strength_benchmark} return`}>
              vs {market.relative_strength_benchmark}, {market.relative_strength_window} sessions
            </th>
          </tr>
        </thead>
        <tbody>
          {market.rows.map((row) => (
            <tr key={row.symbol}>
              <td>
                <Link to={`/symbol/${encodeURIComponent(row.symbol)}`}>{row.symbol}</Link>
                {row.is_benchmark && <span className="tag">benchmark</span>}
                {row.name && <span className="sub">{row.name}</span>}
              </td>
              <td className="num strong">
                {row.values.last_close == null ? (
                  <span className="muted" title={row.unavailable_reason}>
                    unavailable
                  </span>
                ) : (
                  formatNumber(row.values.last_close)
                )}
              </td>
              <td>
                {row.as_of_local
                  ? formatLocal(row.as_of_local, "").trim()
                  : formatDate(row.candle_date)}
              </td>
              <td>
                <FreshnessBadge state={row.freshness} />
              </td>
              <Cell row={row} field="return_1" kind="fraction" />
              <Cell row={row} field="return_5" kind="fraction" />
              <Cell row={row} field="return_20" kind="fraction" />
              <Cell row={row} field="rsi" kind="number" />
              <Cell row={row} field="pct_vs_sma_50" kind="percent" />
              <Cell row={row} field="pct_vs_sma_200" kind="percent" />
              <Cell row={row} field="relative_volume" kind="number" />
              <Cell row={row} field="atr_pct" kind="number" />
              <Cell row={row} field="relative_strength" kind="fraction" />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Watchlist() {
  const { data, error } = useLoad(api.watchlists, "watchlists");
  const [active, setActive] = useState<string | null>(null);

  if (error) {
    return (
      <p className="notice notice-error">
        The backend did not answer ({error}). Start it, then reload this page.
      </p>
    );
  }
  if (!data) return <p className="notice">Loading watchlists…</p>;
  const market = data.markets.find((m) => m.code === active) ?? data.markets[0];
  const empty = market.rows.every((row) => row.candle_date === null);

  return (
    <>
      <h1>Watchlist</h1>
      <div className="tabs" role="tablist" aria-label="Market">
        {data.markets.map((m) => (
          <button
            key={m.code}
            type="button"
            role="tab"
            aria-selected={m.code === market.code}
            className={`tab tab-${m.code}`}
            onClick={() => setActive(m.code)}
          >
            {m.name}
          </button>
        ))}
      </div>
      <section className={`panel market market-${market.code}`} role="tabpanel">
        {empty && (
          <p className="notice notice-warn">
            No data is stored for this market yet. Go to <Link to="/">Overview</Link> and choose
            “Refresh data now”.
          </p>
        )}
        <MarketTable market={market} />
        <p className="footnote">
          Demonstration watchlist from config/watchlists.yaml, not recommendations. Returns and
          indicators use split- and dividend-adjusted closes of completed sessions. A dash means
          the value is unavailable; hover it for the reason. Last completed{" "}
          {market.name} session: {formatDate(market.clock.last_completed_session)}.
        </p>
      </section>
    </>
  );
}
