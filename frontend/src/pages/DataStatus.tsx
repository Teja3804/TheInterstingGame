import { useState } from "react";
import { api, screens, SNAPSHOT, type IngestResponse } from "../api";
import { Section } from "../components/bits";
import { FreshnessBadge } from "../components/FreshnessBadge";
import { formatDate, formatInstant, localClock } from "../format";
import { useLoad } from "../useLoad";

export function DataStatus() {
  const status = useLoad(screens.status, "status-page");
  const [refreshing, setRefreshing] = useState(false);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  async function refresh() {
    setRefreshing(true);
    setProblem(null);
    try {
      setResult(await api.ingest());
    } catch (reason) {
      setProblem(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setRefreshing(false);
      status.reload();
    }
  }

  if (status.error) {
    return (
      <p className="notice notice-error">
        The data status could not be loaded ({status.error}).
      </p>
    );
  }
  if (!status.data) return <p className="notice">Loading status…</p>;
  const { provider, scheduler, markets, symbols, snapshot } = status.data;
  const zoneOf = (code: string) => markets.find((m) => m.code === code)?.clock.timezone ?? "UTC";

  return (
    <>
      <div className="page-head">
        <h1>Data</h1>
        <p className="notice notice-warn" role="status">
          {SNAPSHOT && snapshot
            ? `${snapshot.note} Market clocks below are frozen at that moment.`
            : scheduler.note}
        </p>
      </div>

      <div className="market-grid">
        {markets.map((market) => (
          <section key={market.code} className={`panel market-card market-${market.code}`}>
            <h2>{market.name}</h2>
            <p className="clock">
              <span className="clock-time">{localClock(market.clock.now_local)}</span>
              <span className="clock-zone">
                {formatDate(market.clock.now_local)}, {market.clock.timezone}
              </span>
            </p>
            <p className={market.clock.is_open ? "session session-open" : "session"}>
              {market.clock.is_open ? "Market open" : "Market closed"}
            </p>
            <dl className="facts">
              <dt>Last completed session</dt>
              <dd>{formatDate(market.clock.last_completed_session)}</dd>
              <dt>Next session</dt>
              <dd>{formatDate(market.clock.next_session)}</dd>
              <dt>Currency</dt>
              <dd>{market.currency}</dd>
              <dt>Calendar</dt>
              <dd>
                {market.clock.calendar}, data through{" "}
                {formatDate(market.clock.calendar_valid_through)}
              </dd>
            </dl>
            {market.clock.calendar_warning && (
              <p className="notice notice-warn">{market.clock.calendar_warning}</p>
            )}
            <ul className="counts" aria-label="Data freshness">
              <li>
                <strong>{market.freshness_counts.fresh}</strong> fresh
              </li>
              <li className={market.freshness_counts.stale ? "count-stale" : ""}>
                <strong>{market.freshness_counts.stale}</strong> stale
              </li>
              <li className={market.freshness_counts.missing ? "count-missing" : ""}>
                <strong>{market.freshness_counts.missing}</strong> no data
              </li>
            </ul>
          </section>
        ))}
      </div>

      <Section
        title="Data source"
        aside={
          !SNAPSHOT && (
            <button type="button" className="button" onClick={refresh} disabled={refreshing}>
              {refreshing ? "Refreshing… this takes a few minutes" : "Refresh data now"}
            </button>
          )
        }
      >
        <dl className="facts facts-wide">
          <dt>Source</dt>
          <dd>{provider.label}</dd>
          <dt>Data type</dt>
          <dd>{provider.data_kind}, completed daily candles only</dd>
          <dt>Last successful fetch</dt>
          <dd>
            {provider.last_success_utc
              ? markets
                  .map((m) => formatInstant(provider.last_success_utc, m.clock.timezone))
                  .join(" / ")
              : "Never. Nothing has been fetched yet."}
          </dd>
          <dt>Symbols failing</dt>
          <dd>{provider.symbols_failing.length ? provider.symbols_failing.join(", ") : "None"}</dd>
        </dl>
        {problem && <p className="notice notice-error">Refresh failed: {problem}</p>}
        {result && (
          <p className={result.failed ? "notice notice-error" : "notice"} role="status">
            Refreshed: {result.fetched} fetched, {result.cached} already up to date, {result.failed}{" "}
            failed.
            {result.results
              .filter((row) => row.error)
              .map((row) => ` ${row.symbol}: ${row.error}.`)
              .join("")}
          </p>
        )}
      </Section>

      <Section title="Stored data by symbol">
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
                    {s.symbol}
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
      </Section>
    </>
  );
}
