import { useMemo, useState } from "react";
import { screens, type StrategyRow } from "../api";
import type { MarketCode } from "../App";
import { BacktestTag, pct, r, Section, signed, Warnings } from "../components/bits";
import { CurveChart } from "../components/CurveChart";
import { formatDate, signClass } from "../format";
import { useLoad } from "../useLoad";

// One fixed colour per strategy, in catalogue order. Names are always shown beside them.
const COLORS = ["#1f3a8a", "#b45309", "#0e7490", "#7a3ea8", "#0a7b50", "#be185d"];

function Verdict({ row, current }: { row: StrategyRow; current: StrategyRow }) {
  if (row.is_current) return <span className="tag">current</span>;
  if (row.summary.trades < 30) return <span className="muted">too few trades to judge</span>;
  const gap = row.expectancy_vs_current_r;
  if (gap === null || current.summary.trades < 30) return <span className="muted">–</span>;
  if (Math.abs(gap) < 0.05) return <span className="muted">about the same</span>;
  return (
    <span className={gap > 0 ? "up" : "down"}>
      {r(gap)} per trade {gap > 0 ? "better" : "worse"}
    </span>
  );
}

export function Strategies({ market: code }: { market: MarketCode }) {
  const { data, error } = useLoad(screens.strategies, "strategies");
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const market = data?.markets.find((m) => m.code === code) ?? data?.markets[0];

  const curves = useMemo(
    () =>
      (market?.strategies ?? [])
        .map((s, i) => ({
          key: s.key,
          name: s.name,
          color: COLORS[i % COLORS.length],
          points: s.equity_curve,
          emphasis: s.is_current,
        }))
        .filter((c) => !hidden.has(c.key)),
    [market, hidden],
  );

  if (error) return <p className="notice notice-error">Could not load the comparison ({error}).</p>;
  if (!data || !market) return <p className="notice">Running the strategies…</p>;
  const current = market.strategies.find((s) => s.is_current) ?? market.strategies[0];
  const ranked = [...market.strategies].sort(
    (a, b) => (b.summary.expectancy_r ?? -Infinity) - (a.summary.expectancy_r ?? -Infinity),
  );
  const toggle = (key: string) =>
    setHidden((old) => {
      const next = new Set(old);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  return (
    <>
      <div className="page-head">
        <h1>Strategy comparison</h1>
        <p>
          Six sets of entry and exit rules, each run over the same {market.symbols_tested}{" "}
          {market.name} stocks from {formatDate(market.period.from)} to{" "}
          {formatDate(market.period.to)} with identical stops, targets, time limit and costs. Only
          the rules differ.
        </p>
        <Warnings items={data.warnings} />
      </div>

      <Section title="Results side by side" aside={<BacktestTag />}>
        <div className="table-scroll">
          <table className="compare">
            <thead>
              <tr>
                <th>Strategy</th>
                <th className="num">Trades</th>
                <th className="num">Winners</th>
                <th className="num">Average per trade</th>
                <th>Against current</th>
                <th className="num">Profit factor</th>
                <th className="num">Return with limits</th>
                <th className="num">Deepest drop</th>
                <th className="num">Ends ahead after 20 trades</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map((row) => {
                const color = COLORS[market.strategies.indexOf(row) % COLORS.length];
                return (
                  <tr key={row.key} className={row.is_current ? "is-current" : ""}>
                    <td>
                      <span className="swatch" style={{ background: color }} aria-hidden="true" />
                      <strong>{row.name}</strong>
                      <span className="sub rule">{row.rule}</span>
                    </td>
                    <td className="num">{row.summary.trades}</td>
                    <td className="num">{pct(row.summary.win_rate)}</td>
                    <td className={`num ${signClass(row.summary.expectancy_r)}`}>
                      {r(row.summary.expectancy_r)}
                    </td>
                    <td>
                      <Verdict row={row} current={current} />
                    </td>
                    <td className="num">
                      {row.summary.profit_factor === null
                        ? "–"
                        : row.summary.profit_factor.toFixed(2)}
                    </td>
                    <td className={`num ${signClass(row.portfolio.total_return_pct)}`}>
                      {signed(row.portfolio.total_return_pct)}
                    </td>
                    <td className="num down">{signed(row.portfolio.max_drawdown_pct)}</td>
                    <td className="num">
                      {row.probability.available ? (
                        pct(row.probability.prob_profit)
                      ) : (
                        <span className="muted" title={row.probability.reason}>
                          too few trades
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="footnote">
          Sorted by average result per trade (R = the planned loss if the stop is hit). "Return
          with limits" allows at most {current.portfolio.max_positions} positions at once.
          Buying and holding {market.benchmark.symbol} over the same period returned{" "}
          {signed(market.benchmark.buy_and_hold_return_pct)}. {market.benchmark.note}
        </p>
      </Section>

      <Section title="Cumulative return over time" aside={<BacktestTag />}>
        <div className="legend" role="group" aria-label="Show or hide strategies">
          {market.strategies.map((s, i) => (
            <label key={s.key} className="legend-item">
              <input type="checkbox" checked={!hidden.has(s.key)} onChange={() => toggle(s.key)} />
              <span className="swatch" style={{ background: COLORS[i % COLORS.length] }} />
              {s.name}
            </label>
          ))}
        </div>
        <CurveChart curves={curves} label={`Cumulative return of each strategy in ${market.name}`} />
        <p className="footnote">
          Each line risks {data.execution.risk_per_trade_pct}% of equity per trade with at most{" "}
          {current.portfolio.max_positions} positions open. The current strategy is the thicker
          line.
        </p>
      </Section>

      <Section title={`What each strategy says today, ${formatDate(market.as_of)}`}>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Strategy</th>
                <th>New buy signals on the latest candle</th>
                <th>Simulated trades still open</th>
              </tr>
            </thead>
            <tbody>
              {market.strategies.map((row) => (
                <tr key={row.key}>
                  <td>
                    <strong>{row.name}</strong>
                  </td>
                  <td className="wrap">
                    {row.signals_now.length ? row.signals_now.join(", ") : "None"}
                  </td>
                  <td className="wrap">
                    {row.in_trade_now.length ? row.in_trade_now.join(", ") : "None"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="footnote">
          Signals are read at the close and would fill at the next session's open. They are rule
          outputs on current data, not recommendations.
        </p>
      </Section>
    </>
  );
}
