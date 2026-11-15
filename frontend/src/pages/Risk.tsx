import { useMemo } from "react";
import { screens, type Bucket, type RiskMarket } from "../api";
import type { MarketCode } from "../App";
import { BacktestTag, pct, r, Section, signed, Stat, Warnings } from "../components/bits";
import { CurveChart } from "../components/CurveChart";
import { formatDate, signClass } from "../format";
import { useLoad } from "../useLoad";

const tone = (value: number | null | undefined) =>
  value === null || value === undefined || value === 0 ? undefined : value > 0 ? "up" : "down";

/** Share of resampled outcomes, drawn as a filled bar with the figure beside it. */
function Odds({ label, value, detail }: { label: string; value: number; detail: string }) {
  return (
    <div className="odds">
      <div className="odds-head">
        <span>{label}</span>
        <strong>{pct(value)}</strong>
      </div>
      <div className="odds-track" aria-hidden="true">
        <div className="odds-fill" style={{ width: `${value * 100}%` }} />
      </div>
      <p className="stat-hint">{detail}</p>
    </div>
  );
}

function BucketTable({ title, note, rows }: { title: string; note: string; rows: Bucket[] }) {
  const scale = Math.max(0.05, ...rows.map((b) => Math.abs(b.expectancy_r ?? 0)));
  return (
    <div>
      <h3>{title}</h3>
      <table className="bucket">
        <thead>
          <tr>
            <th>When</th>
            <th className="num">Trades</th>
            <th className="num">Winners</th>
            <th className="num">Average per trade</th>
            <th aria-hidden="true" />
          </tr>
        </thead>
        <tbody>
          {rows.map((b) => {
            const value = b.expectancy_r ?? 0;
            const width = `${(Math.abs(value) / scale) * 50}%`;
            return (
              <tr key={b.name}>
                <td>{b.name}</td>
                <td className="num">{b.trades}</td>
                <td className="num">{pct(b.win_rate)}</td>
                <td className={`num ${signClass(b.expectancy_r)}`}>{r(b.expectancy_r)}</td>
                <td className="diverge" aria-hidden="true">
                  <span
                    className={value >= 0 ? "diverge-bar up" : "diverge-bar down"}
                    style={value >= 0 ? { left: "50%", width } : { right: "50%", width }}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="footnote">{note}</p>
    </div>
  );
}

function MarketRisk({ market, riskPct }: { market: RiskMarket; riskPct: number }) {
  const s = market.summary;
  const p = market.probability;
  const limits = market.loss_limits;
  const curves = useMemo(
    () => [
      {
        name: "Current strategy",
        color: "#1f3a8a",
        points: market.equity_curve,
        emphasis: true,
      },
    ],
    [market.equity_curve],
  );

  if (s.trades === 0) {
    return (
      <p className="notice notice-warn">
        The current strategy made no completed trades in the stored {market.name} history, so
        there is nothing to analyse yet.
      </p>
    );
  }

  return (
    <>
      <section className="panel">
        <div className="panel-head">
          <h2>
            What the past says, {formatDate(market.period.from)} to {formatDate(market.period.to)}
          </h2>
          <BacktestTag />
        </div>
        <div className="stat-row">
          <Stat
            label="Trades tested"
            value={s.trades}
            hint={`${market.symbols_tested} stocks, about ${s.avg_holding_sessions?.toFixed(0)} sessions each`}
          />
          <Stat
            label="Winners"
            value={pct(s.win_rate)}
            hint={`likely range ${pct(s.win_rate_low)} to ${pct(s.win_rate_high)}`}
          />
          <Stat
            label="Average per trade"
            value={r(s.expectancy_r)}
            tone={tone(s.expectancy_r)}
            hint={`wins ${r(s.avg_win_r)}, losses ${r(s.avg_loss_r)}`}
          />
          <Stat
            label="Profit factor"
            value={s.profit_factor === null ? "–" : s.profit_factor.toFixed(2)}
            hint="gains divided by losses; above 1 made money"
          />
          <Stat
            label="Return with limits"
            value={signed(market.portfolio.total_return_pct)}
            tone={tone(market.portfolio.total_return_pct)}
            hint={`${market.portfolio.trades_taken} trades taken, ${market.portfolio.signals_skipped} skipped`}
          />
          <Stat
            label="Deepest drop"
            value={signed(market.portfolio.max_drawdown_pct)}
            tone="down"
            hint="largest fall from a peak, with limits"
          />
        </div>
        <ul className="findings">
          {market.findings.map((finding) => (
            <li key={finding}>{finding}</li>
          ))}
        </ul>
        <CurveChart
          curves={curves}
          label={`Cumulative return of the current strategy in ${market.name}`}
        />
        <p className="footnote">
          Cumulative return risking {riskPct}% of equity per trade. {market.portfolio.note} R is
          the planned loss if the stop is hit, so +2 R is a gain twice that size.
        </p>
      </section>

      <Section title="Chances over the next 20 trades" aside={<BacktestTag />}>
        {p.available ? (
          <>
            <div className="odds-grid">
              <Odds
                label="Ends ahead"
                value={p.prob_profit}
                detail={`middle outcome ${signed(p.return_p50_pct)}, usual range ${signed(p.return_p05_pct)} to ${signed(p.return_p95_pct)}`}
              />
              <Odds
                label={`Drops ${p.drawdown_threshold_pct}% or more along the way`}
                value={p.prob_drawdown}
                detail={`1 run in 20 fell ${signed(p.worst_drawdown_p95_pct)} or worse`}
              />
              <Odds
                label={`${p.losing_streak} losses in a row`}
                value={p.prob_losing_streak}
                detail={`longest losing run actually seen: ${s.longest_losing_streak}`}
              />
            </div>
            <p className="footnote">
              From {p.paths.toLocaleString("en-US")} reshuffles of the {p.sample_trades} past
              trades, {p.horizon_trades} trades each, risking {riskPct}% per trade. This assumes
              future trades resemble past ones and do not depend on each other. Real losses tend
              to cluster, so streaks are likely understated. These are frequencies in past data,
              not a forecast.
            </p>
          </>
        ) : (
          <p className="notice notice-warn">Unavailable: {p.reason}.</p>
        )}
      </Section>

      <Section title="When does it work, and when does it fail?" aside={<BacktestTag />}>
        <div className="bucket-grid">
          <BucketTable
            title="If volatility changes"
            note="Market volatility on the day of the signal, compared with its own recent range."
            rows={market.by_volatility}
          />
          <BucketTable
            title="By market regime"
            note="Regime of the benchmark index on the day of the signal."
            rows={market.by_regime}
          />
          <BucketTable
            title="Earlier versus later"
            note="A strategy that only worked in one half deserves less trust."
            rows={market.by_period}
          />
        </div>
      </Section>

      <Section title="What if conditions are harsher than assumed?" aside={<BacktestTag />}>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Assumption</th>
                <th className="num">Average per trade</th>
                <th className="num">Winners</th>
                <th className="num">Return, every signal taken</th>
                <th className="num">Deepest drop</th>
              </tr>
            </thead>
            <tbody>
              {market.stress.map((row) => (
                <tr key={row.name}>
                  <td>{row.name}</td>
                  <td className={`num ${signClass(row.expectancy_r)}`}>{r(row.expectancy_r)}</td>
                  <td className="num">{pct(row.win_rate)}</td>
                  <td className={`num ${signClass(row.total_return_pct)}`}>
                    {signed(row.total_return_pct)}
                  </td>
                  <td className="num down">{signed(row.max_drawdown_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="footnote">
          The same past trades, restated with higher costs and worse fills on every stop. These
          rows take every signal, so their returns differ from the limited portfolio above.
        </p>
      </Section>

      <Section title="How big can a loss get, and what stops it?">
        <div className="stat-row">
          <Stat
            label="Planned loss per trade"
            value={`−${limits.risk_per_trade_pct}%`}
            hint="of equity, if the stop fills as planned"
          />
          <Stat
            label="Worst trade in the test"
            value={r(limits.worst_tested_trade_r)}
            tone="down"
            hint={`${signed(limits.worst_tested_trade_pct_of_equity, 2)} of equity; ${s.gap_stops} stops were jumped by a gap`}
          />
          <Stat
            label="All stops hit together"
            value={`−${limits.max_open_risk_pct}%`}
            hint={`at most ${limits.max_simultaneous_trades_at_full_risk} trades open at full risk`}
          />
          <Stat
            label={`Every open trade gaps ${limits.hypothetical_gap_r}x`}
            value={signed(limits.all_open_trades_gap_pct_of_equity)}
            tone="down"
            hint="a hypothetical bad overnight shock, not a tested result"
          />
        </div>
        <ul className="findings">
          <li>
            A stop limits the loss only if the price trades through it. An overnight gap skips
            the stop, and the loss is taken at the open.
          </li>
          <li>
            The size limits are what cap the damage: {limits.risk_per_trade_pct}% of equity per
            trade and {limits.max_open_risk_pct}% across all open trades.
          </li>
          <li>The system never averages down and never moves a stop lower.</li>
          <li>When the market regime turns Bearish, new entries are held back.</li>
        </ul>
      </Section>

      {market.open_trades.length > 0 && (
        <Section title="Trades the strategy would be in now" aside={<BacktestTag />}>
          <p>
            {market.open_trades.map((t) => `${t.symbol} since ${formatDate(t.entry_date)}`).join(", ")}.
            Simulated positions only; they are left out of the statistics above.
          </p>
        </Section>
      )}
    </>
  );
}

export function Risk({ market: code }: { market: MarketCode }) {
  const { data, error } = useLoad(screens.risk, "risk");
  if (error) return <p className="notice notice-error">Could not load the analysis ({error}).</p>;
  if (!data) return <p className="notice">Running the analysis…</p>;
  const market = data.markets.find((m) => m.code === code) ?? data.markets[0];
  return (
    <>
      <div className="page-head">
        <h1>Risk analysis of the current strategy</h1>
        <p>
          <strong>{data.strategy.name}.</strong> {data.strategy.rule} {data.execution.fills}{" "}
          Stop: {data.execution.stop} Target: {data.execution.target} Time exit:{" "}
          {data.execution.time_exit.toLowerCase()}
        </p>
        <Warnings items={data.warnings} />
      </div>
      <MarketRisk key={market.code} market={market} riskPct={data.execution.risk_per_trade_pct} />
    </>
  );
}
