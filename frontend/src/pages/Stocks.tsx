import { useContext, useEffect, useState } from "react";
import { screens, type Quote, type StocksMarket } from "../api";
import type { MarketCode } from "../App";
import { ActionChip, ScoreMeter, Spark } from "../components/bits";
import { quoteTimeLabel } from "../components/LatestPrice";
import { FreshnessBadge } from "../components/FreshnessBadge";
import { formatDate, formatFraction, formatNumber, formatPercent, signClass } from "../format";
import { positionStore, type Position } from "../positions";
import { QuotesContext } from "../quotes";
import { useLoad } from "../useLoad";
import { StockPanel } from "./StockPanel";

type SortKey = "score" | "return_20" | "symbol";

function RegimeBanner({ market }: { market: StocksMarket }) {
  const { regime } = market;
  return (
    <div className={`regime regime-${regime.label.toLowerCase()}`}>
      <div>
        <span className="regime-label">
          {market.name} market: {regime.label}
        </span>
        <span className="regime-date">
          {regime.as_of ? `as of ${formatDate(regime.as_of)}` : "no benchmark data"}
        </span>
      </div>
      <p>{regime.evidence.join(". ")}.</p>
    </div>
  );
}

function StockPrice({
  quote,
  lastClose,
  return20,
  zone,
}: {
  quote: Quote | undefined;
  lastClose: number | null | undefined;
  return20: number | null | undefined;
  zone: string;
}) {
  const live = quote && quote.price !== null ? quote : undefined;
  return (
    <span
      className="stock-price"
      title={live ? quoteTimeLabel(live, zone) : "Last completed close"}
    >
      <span>{formatNumber(live ? live.price : lastClose)}</span>
      {live && (
        <span className={`sub ${signClass(live.change_pct)}`}>
          {formatPercent(live.change_pct)} {live.kind === "during_session" ? "today" : "day"}
        </span>
      )}
      <span className={`sub ${signClass(return20)}`}>{formatFraction(return20, 1)} in 20</span>
    </span>
  );
}

export function Stocks({ market: code }: { market: MarketCode }) {
  const { data, error } = useLoad(screens.stocks, "stocks");
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [sort, setSort] = useState<SortKey>("score");
  const [positions, setPositions] = useState<Position[]>([]);
  const quotes = useContext(QuotesContext);

  useEffect(() => {
    let stop = () => {};
    let cancelled = false;
    void positionStore().then((store) => {
      if (!cancelled) stop = store.subscribe(setPositions);
    });
    return () => {
      cancelled = true;
      stop();
    };
  }, []);

  if (error) {
    return (
      <p className="notice notice-error">
        The data could not be loaded ({error}). Check that the backend is running, then reload.
      </p>
    );
  }
  if (!data) return <p className="notice">Loading stocks…</p>;
  const market = data.markets.find((m) => m.code === code) ?? data.markets[0];
  const held = new Set(positions.map((p) => p.symbol));
  const rows = [...market.rows].sort((a, b) => {
    if (sort === "symbol") return a.symbol.localeCompare(b.symbol);
    const left = sort === "score" ? a.score : a.values.return_20;
    const right = sort === "score" ? b.score : b.values.return_20;
    return (right ?? -Infinity) - (left ?? -Infinity);
  });
  const current = selected[market.code] ?? rows[0]?.symbol;
  const quoteOf = (symbol: string) =>
    quotes?.markets.find((m) => m.code === market.code)?.quotes.find((q) => q.symbol === symbol);
  const empty = market.rows.every((row) => row.candle_date === null);

  return (
    <>
      <RegimeBanner market={market} />
      {empty && (
        <p className="notice notice-warn">
          No prices are stored for this market yet. Open the Data screen and refresh.
        </p>
      )}
      <div className="split">
        <section className="panel list-panel" aria-label={`${market.name} stocks`}>
          <div className="panel-head">
            <h2>{market.rows.length} stocks</h2>
            <label className="sorter">
              Sort by
              <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
                <option value="score">Score</option>
                <option value="return_20">20-session return</option>
                <option value="symbol">Symbol</option>
              </select>
            </label>
          </div>
          <ul className="stock-list">
            {rows.map((row) => (
              <li key={row.symbol}>
                <button
                  type="button"
                  className={row.symbol === current ? "stock-row selected" : "stock-row"}
                  aria-pressed={row.symbol === current}
                  onClick={() => setSelected((s) => ({ ...s, [market.code]: row.symbol }))}
                >
                  <span className="stock-id">
                    <span className="stock-symbol">
                      {row.symbol}
                      {held.has(row.symbol) && <span className="tag tag-held">held</span>}
                    </span>
                    <span className="sub">{row.name ?? "Name unavailable"}</span>
                  </span>
                  <Spark values={row.spark} />
                  <StockPrice
                    quote={quoteOf(row.symbol)}
                    lastClose={row.values.last_close}
                    return20={row.values.return_20}
                    zone={market.timezone}
                  />
                  <span className="stock-verdict">
                    <ScoreMeter score={row.score} compact />
                    <ActionChip action={row.suggestion.action} />
                  </span>
                  {row.freshness !== "fresh" && <FreshnessBadge state={row.freshness} />}
                </button>
              </li>
            ))}
          </ul>
          <p className="footnote">
            {data.note} Buy candidate: score {data.thresholds.buy_candidate} or more with no
            rejection. Watch: {data.thresholds.watch} or more. Prices in {market.currency}: the
            latest delayed price where one is published (hover for its time), otherwise the close
            of the last completed session {formatDate(market.last_completed_session)}. The lists
            are a configurable selection of large companies, not recommendations.
          </p>
        </section>
        <div className="detail-column">
          {current && (
            <StockPanel
              key={current}
              symbol={current}
              position={positions.find((p) => p.symbol === current) ?? null}
              onPick={(symbol) => setSelected((s) => ({ ...s, [market.code]: symbol }))}
            />
          )}
        </div>
      </div>
    </>
  );
}
