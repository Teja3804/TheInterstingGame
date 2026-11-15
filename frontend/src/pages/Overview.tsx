import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type IngestResponse, type SourcesStatus } from "../api";
import { FreshnessBadge } from "../components/FreshnessBadge";
import { formatDate, formatInstant, localClock } from "../format";
import { useLoad } from "../useLoad";

type Market = SourcesStatus["markets"][number];

function MarketPanel({ market }: { market: Market }) {
  const { clock, freshness_counts: counts } = market;
  return (
    <section className={`panel market market-${market.code}`} aria-label={`${market.name} market`}>
      <h2>{market.name}</h2>
      <p className="clock">
        <span className="clock-time">{localClock(clock.now_local)}</span>
        <span className="clock-zone">
          {formatDate(clock.now_local)}, {clock.timezone}
        </span>
      </p>
      <p className={clock.is_open ? "session session-open" : "session"}>
        {clock.is_open ? "Market open" : "Market closed"}
      </p>
      <dl className="facts">
        <dt>Last completed session</dt>
        <dd>{formatDate(clock.last_completed_session)}</dd>
        <dt>Next session</dt>
        <dd>{formatDate(clock.next_session)}</dd>
        <dt>Currency</dt>
        <dd>{market.currency}</dd>
        <dt>Calendar</dt>
        <dd>
          {clock.calendar}, data through {formatDate(clock.calendar_valid_through)}
        </dd>
      </dl>
      {clock.calendar_warning && <p className="notice notice-warn">{clock.calendar_warning}</p>}
      <ul className="counts" aria-label="Data freshness">
        <li>
          <strong>{counts.fresh}</strong> fresh
        </li>
        <li className={counts.stale ? "count-stale" : ""}>
          <strong>{counts.stale}</strong> stale
        </li>
        <li className={counts.missing ? "count-missing" : ""}>
          <strong>{counts.missing}</strong> no data
        </li>
      </ul>
    </section>
  );
}

export function Overview() {
  const status = useLoad(api.status, "status");
  const [refreshing, setRefreshing] = useState(false);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  async function refresh() {
    setRefreshing(true);
    setRefreshError(null);
    try {
      setResult(await api.ingest());
    } catch (reason) {
      setRefreshError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setRefreshing(false);
      status.reload();
    }
  }

  if (status.error) {
    return (
      <p className="notice notice-error">
        The backend did not answer ({status.error}). Start it, then reload this page.
      </p>
    );
  }
  if (!status.data) return <p className="notice">Loading status…</p>;
  const { provider, scheduler, markets, symbols } = status.data;
  const zoneOf = (code: string) => markets.find((m) => m.code === code)?.clock.timezone ?? "UTC";

  return (
    <>
      <h1>Overview</h1>
      <p className="notice notice-warn" role="status">
        {scheduler.note}
      </p>

      <div className="market-grid">
        {markets.map((market) => (
          <MarketPanel key={market.code} market={market} />
        ))}
      </div>

      <section className="panel">
        <div className="panel-head">
          <h2>Data source</h2>
          <button type="button" onClick={refresh} disabled={refreshing}>
            {refreshing ? "Refreshing… this can take a minute" : "Refresh data now"}
          </button>
        </div>
        <dl className="facts facts-wide">
          <dt>Source</dt>
          <dd>{provider.label}</dd>
          <dt>Data type</dt>
          <dd>{provider.data_kind}, completed daily candles only</dd>
          <dt>Last successful fetch</dt>
          <dd>
            {provider.last_success_utc
              ? markets.map((m) => formatInstant(provider.last_success_utc, m.clock.timezone)).join(" / ")
              : "Never. Nothing has been fetched yet."}
          </dd>
          <dt>Symbols failing</dt>
          <dd>{provider.symbols_failing.length ? provider.symbols_failing.join(", ") : "None"}</dd>
        </dl>
        {refreshError && <p className="notice notice-error">Refresh failed: {refreshError}</p>}
        {result && (
          <p className={result.failed ? "notice notice-error" : "notice"} role="status">
            Refreshed: {result.fetched} fetched, {result.cached} already up to date, {result.failed}{" "}
            failed.
            {result.results
              .filter((r) => r.error)
              .map((r) => ` ${r.symbol}: ${r.error}.`)
              .join("")}
          </p>
        )}
      </section>

      <section className="panel">
        <h2>Stored data by symbol</h2>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Market</th>
                <th>Freshness</th>
                <th>Latest candle</th>
                <th className="num">Candles</th>
                <th>Last successful fetch</th>
                <th className="num">Warnings</th>
                <th>Last error</th>
              </tr>
            </thead>
            <tbody>
              {symbols.map((s) => (
                <tr key={s.symbol}>
                  <td>
                    <Link to={`/symbol/${encodeURIComponent(s.symbol)}`}>{s.symbol}</Link>
                    {s.is_benchmark && <span className="tag">benchmark</span>}
                  </td>
                  <td>{s.market}</td>
                  <td>
                    <FreshnessBadge state={s.freshness} />
                  </td>
                  <td>{formatDate(s.latest_candle_date)}</td>
                  <td className="num">{s.stored_rows}</td>
                  <td>{formatInstant(s.last_success_utc, zoneOf(s.market))}</td>
                  <td className="num">{s.quality_issue_count}</td>
                  <td className="error-text">{s.last_outcome === "failed" ? s.last_error : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
