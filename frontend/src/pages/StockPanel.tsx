import { useEffect, useState, type FormEvent } from "react";
import { screens, type Insight, type SymbolBundle } from "../api";
import { ActionChip, BacktestTag, pct, r, ScoreMeter, Section } from "../components/bits";
import { Price } from "../components/Price";
import { PriceChart, type Overlays } from "../components/PriceChart";
import {
  formatDate,
  formatFraction,
  formatInstant,
  formatLocal,
  formatNumber,
  formatPercent,
  signClass,
} from "../format";
import { viewPosition } from "../positionMath";
import { newId, positionStore, type Position, type StoreKind } from "../positions";
import { useLoad } from "../useLoad";

const STORE_TEXT: Record<StoreKind, string> = {
  hosted: "Saved with this page, so it is there on your other devices too.",
  browser: "Saved in this browser only.",
  memory: "This browser blocks storage, so the position is kept only until you close the page.",
};

function inputValue(value: number | null, kind: string, currency: string): string {
  if (value === null) return "unavailable";
  if (kind === "pct") return formatPercent(value);
  if (kind === "price") return `${formatNumber(value)} ${currency}`;
  return formatNumber(value);
}

function ScoreBreakdown({ insight, currency }: { insight: Insight; currency: string }) {
  const dropped = insight.weight_used !== null && insight.weight_used < 100;
  return (
    <Section title="Why this score" aside={<ScoreMeter score={insight.score} />}>
      <ul className="components">
        {insight.components.map((component) => (
          <li key={component.key}>
            <div className="component-head">
              <span className="component-name">
                {component.label} <span className="muted">weight {component.weight}%</span>
              </span>
              {component.score === null ? (
                <span className="muted">{component.unavailable_reason}</span>
              ) : (
                <ScoreMeter score={component.score} />
              )}
            </div>
            <p className="component-formula">{component.formula}</p>
            <p className="component-inputs">
              {component.inputs
                .map((i) => `${i.label}: ${inputValue(i.value, i.kind, currency)}`)
                .join("  |  ")}
            </p>
          </li>
        ))}
      </ul>
      {dropped && (
        <p className="footnote">
          Unavailable parts are left out and the rest rescaled: this score uses{" "}
          {insight.weight_used}% of the weights.
        </p>
      )}
      <div className="for-against">
        <div>
          <h3>In favour</h3>
          {insight.bullish.length ? (
            <ul>
              {insight.bullish.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">Nothing stands out.</p>
          )}
        </div>
        <div>
          <h3>Against</h3>
          {insight.bearish.length ? (
            <ul>
              {insight.bearish.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">Nothing stands out.</p>
          )}
        </div>
      </div>
      {insight.not_checked.map((note) => (
        <p key={note} className="notice notice-warn">
          {note}
        </p>
      ))}
    </Section>
  );
}

function Plan({ insight, currency }: { insight: Insight; currency: string }) {
  const plan = insight.plan;
  if (!plan) {
    return (
      <Section title="Trade plan">
        <p className="muted">Unavailable: not enough history to measure volatility (ATR).</p>
      </Section>
    );
  }
  const money = (v: number) => `${formatNumber(v)} ${currency}`;
  return (
    <Section title="Trade plan if you were to buy">
      <div className="levels-row">
        <div className="level level-stop">
          <span>Stop</span>
          <strong>{money(plan.stop)}</strong>
          <small>{plan.stop_rule}</small>
        </div>
        <div className="level">
          <span>Entry reference</span>
          <strong>{money(plan.entry_reference)}</strong>
          <small>last close</small>
        </div>
        <div className="level level-target">
          <span>Target</span>
          <strong>{money(plan.target)}</strong>
          <small>{plan.target_rule}</small>
        </div>
      </div>
      <dl className="facts facts-wide">
        <dt>Entry condition</dt>
        <dd>{plan.entry_condition}</dd>
        <dt>Risk per share</dt>
        <dd>
          {money(plan.risk_per_share)} ({formatNumber(plan.risk_pct_of_price, 1)}% of price)
        </dd>
        <dt>Reward/risk after costs</dt>
        <dd>
          {formatNumber(plan.reward_risk_after_costs)} (estimated round-trip cost{" "}
          {formatNumber(plan.estimated_round_trip_cost_pct)}%)
        </dd>
        <dt>Holding limit</dt>
        <dd>{plan.max_holding_sessions} sessions (about 30 days)</dd>
        <dt>Size</dt>
        <dd>
          {plan.sizing.shares} shares, {money(plan.sizing.position_value)}, risking{" "}
          {money(plan.sizing.risk_amount)}. Limited by: {plan.sizing.binding_constraint}.
        </dd>
        <dt>If it gaps through the stop</dt>
        <dd>
          A {plan.sizing.gap_r_multiple}x gap would lose about {money(plan.sizing.gap_loss_amount)},
          not the planned {money(plan.sizing.risk_amount)}.
        </dd>
      </dl>
      <p className="footnote">
        {plan.sizing.note} Example portfolio: {money(plan.sizing.example_equity)}.
      </p>
      <ol className="scenarios">
        {plan.scenarios.map((s) => (
          <li key={s.name} className={`scenario scenario-${s.name.toLowerCase()}`}>
            <strong>{s.name}</strong>
            <span>{s.text}</span>
            <span className="muted">What would change the plan: {s.changes_the_plan}</span>
          </li>
        ))}
      </ol>
    </Section>
  );
}

function PositionCard({ bundle, position }: { bundle: SymbolBundle; position: Position | null }) {
  const { insight, prices } = bundle;
  const [kind, setKind] = useState<StoreKind | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const lastClose = prices.bars.at(-1)?.close ?? null;
  const currency = prices.currency;

  useEffect(() => {
    void positionStore().then((store) => setKind(store.kind));
  }, []);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const quantity = Number(form.get("quantity"));
    const entryPrice = Number(form.get("entry_price"));
    const entryDate = String(form.get("entry_date") ?? "");
    if (!(quantity > 0) || !(entryPrice > 0) || !/^\d{4}-\d{2}-\d{2}$/.test(entryDate)) {
      setProblem("Enter a quantity and price above zero, and the date you bought.");
      return;
    }
    try {
      const store = await positionStore();
      await store.save({
        id: position?.id ?? newId(),
        symbol: prices.symbol,
        quantity,
        entry_price: entryPrice,
        entry_date: entryDate,
      });
      setProblem(null);
      setEditing(false);
    } catch {
      setProblem("The position could not be saved. You may only have view access to this page.");
    }
  }

  async function remove() {
    if (!position) return;
    try {
      await (await positionStore()).remove(position.id);
    } catch {
      setProblem("The position could not be removed.");
    }
  }

  const form = (
    <form className="position-form" onSubmit={save}>
      <label>
        Quantity
        <input
          name="quantity"
          type="number"
          min="0"
          step="any"
          defaultValue={position?.quantity}
          required
        />
      </label>
      <label>
        Entry price ({currency})
        <input
          name="entry_price"
          type="number"
          min="0"
          step="any"
          defaultValue={position?.entry_price}
          required
        />
      </label>
      <label>
        Entry date
        <input name="entry_date" type="date" defaultValue={position?.entry_date} required />
      </label>
      <button type="submit" className="button">
        {position ? "Save changes" : "Save position"}
      </button>
      {position && (
        <button type="button" className="button button-quiet" onClick={() => setEditing(false)}>
          Cancel
        </button>
      )}
    </form>
  );

  if (!position || lastClose === null) {
    return (
      <Section title="Your position">
        <p>
          You have no position recorded in {prices.symbol}. Add one to see whether the rules say
          hold, exit or hedge. Nothing is sent to a broker.
        </p>
        {lastClose === null ? <p className="muted">Unavailable until prices are stored.</p> : form}
        {problem && <p className="notice notice-error">{problem}</p>}
        {kind && <p className="footnote">{STORE_TEXT[kind]}</p>}
      </Section>
    );
  }

  const view = viewPosition(
    position,
    lastClose,
    prices.bars.map((b) => b.date),
    insight.if_held.max_holding_sessions,
    insight.hedge.beta,
  );
  const money = (v: number) => `${formatNumber(v)} ${currency}`;
  const held = insight.if_held;
  return (
    <Section title="Your position" aside={<ActionChip action={held.action} large />}>
      <ul className="reasons">
        {held.reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
        {view.pastTimeLimit && (
          <li>
            Held {view.sessionsHeldIsMinimum ? "at least " : ""}
            {view.sessionsHeld} sessions, past the {held.max_holding_sessions}-session limit: the
            plan calls for a time-based exit.
          </li>
        )}
      </ul>
      <div className="stat-row">
        <div className="stat">
          <div className="stat-label">Unrealised result</div>
          <div className={`stat-value ${signClass(view.pnl)}`}>
            {view.pnl >= 0 ? "+" : "−"}
            {money(Math.abs(view.pnl))}
          </div>
          <div className="stat-hint">{formatFraction(view.pnlFraction)} on cost</div>
        </div>
        <div className="stat">
          <div className="stat-label">Value now</div>
          <div className="stat-value">{money(view.value)}</div>
          <div className="stat-hint">
            {position.quantity} at {money(position.entry_price)}
          </div>
        </div>
        <div className="stat">
          <div className="stat-label">Sessions held</div>
          <div className="stat-value">
            {view.sessionsHeldIsMinimum ? "≥ " : ""}
            {view.sessionsHeld}
          </div>
          <div className="stat-hint">
            since {formatDate(position.entry_date)}, limit {held.max_holding_sessions}
          </div>
        </div>
        <div className="stat">
          <div className="stat-label">Trailing stop</div>
          <div className="stat-value">
            {held.trailing_stop === null ? "–" : money(held.trailing_stop)}
          </div>
          <div className="stat-hint">exit on a close below it</div>
        </div>
      </div>
      {held.action !== "Hold" && (
        <>
          <h3>Choices to compare</h3>
          <ul className="reasons">
            {held.options.map((option) => (
              <li key={option}>{option}</li>
            ))}
          </ul>
        </>
      )}
      <h3>Hedge estimate</h3>
      {insight.hedge.beta === null ? (
        <p className="muted">Unavailable: {insight.hedge.unavailable_reason}.</p>
      ) : (
        <p>
          Beta to {insight.hedge.benchmark} over {insight.hedge.beta_sessions} sessions is{" "}
          <strong>{formatNumber(insight.hedge.beta)}</strong>. Offsetting this position's market
          sensitivity would take about <strong>{money(view.hedgeValue ?? 0)}</strong> of index
          exposure (reference: {insight.hedge.instrument}). The index explained about{" "}
          {formatNumber(insight.hedge.variance_explained_pct, 0)}% of this stock's daily moves, so
          the rest would stay unhedged.
        </p>
      )}
      <details className="warnings">
        <summary>Limits of a hedge</summary>
        <ul>
          {insight.hedge.limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </details>
      {editing ? (
        form
      ) : (
        <p className="button-row">
          <button type="button" className="button button-quiet" onClick={() => setEditing(true)}>
            Edit position
          </button>
          <button type="button" className="button button-quiet" onClick={remove}>
            Remove position
          </button>
        </p>
      )}
      {problem && <p className="notice notice-error">{problem}</p>}
      <p className="footnote">
        The advice ignores your purchase price on purpose: whether to keep holding depends on
        where the stock is now. {kind ? STORE_TEXT[kind] : ""}
      </p>
    </Section>
  );
}

export function StockPanel({
  symbol,
  position,
  onPick,
}: {
  symbol: string;
  position: Position | null;
  onPick: (symbol: string) => void;
}) {
  const { data, error } = useLoad(() => screens.symbol(symbol), `symbol:${symbol}`);
  const [overlays, setOverlays] = useState<Overlays>({
    sma: true,
    ema: false,
    bollinger: false,
    levels: true,
  });

  if (error) {
    return (
      <p className="notice notice-error">
        Could not load {symbol} ({error}).
      </p>
    );
  }
  if (!data) return <p className="notice">Loading {symbol}…</p>;
  const { prices, indicators, insight } = data;
  if (!insight.available || prices.bars.length === 0) {
    return (
      <p className="notice notice-warn">
        {symbol} is unavailable: {insight.reason ?? "no data stored"}.
      </p>
    );
  }
  const zone = indicators.timezone;
  const history = insight.backtest_history;
  const toggle = (key: keyof Overlays) => setOverlays((o) => ({ ...o, [key]: !o[key] }));

  return (
    <>
      <section className="panel hero">
        <div className="hero-top">
          <div>
            <h1>{symbol}</h1>
            <p className="sub">
              {indicators.profile?.name ?? "Name unavailable"}
              {indicators.profile?.sector ? `, ${indicators.profile.sector}` : ""}
            </p>
          </div>
          <Price value={indicators.snapshot.last_close} from={indicators} size="large" />
        </div>
        <div className="verdict">
          <ActionChip action={insight.suggestion.action} large />
          <ul className="reasons">
            {insight.suggestion.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
        <p className="footnote">{insight.label_note}</p>
      </section>

      <PositionCard bundle={data} position={position} />

      <section className="panel">
        <div className="panel-head">
          <h2>Price history, adjusted for splits and dividends</h2>
          <fieldset className="toggles">
            <legend className="visually-hidden">Chart overlays</legend>
            {(
              [
                ["sma", "Averages 20 / 50 / 200"],
                ["ema", "EMA 9 / 21"],
                ["bollinger", "Bollinger Bands"],
                ["levels", "Support and resistance"],
              ] as [keyof Overlays, string][]
            ).map(([key, label]) => (
              <label key={key}>
                <input type="checkbox" checked={overlays[key]} onChange={() => toggle(key)} />
                {label}
              </label>
            ))}
          </fieldset>
        </div>
        <PriceChart prices={prices} indicators={indicators} overlays={overlays} />
        <p className="footnote">
          Daily candles with volume, then RSI 14 and MACD. Candle used:{" "}
          {indicators.as_of_local
            ? formatLocal(indicators.as_of_local, zone)
            : formatDate(indicators.candle_date)}
          . Fetched {formatInstant(indicators.fetched_at_utc, zone)}. Source:{" "}
          {indicators.source_label}.
        </p>
      </section>

      <ScoreBreakdown insight={insight} currency={indicators.currency} />
      <Plan insight={insight} currency={indicators.currency} />

      <Section title="Stronger alternatives right now">
        {insight.alternatives.length === 0 ? (
          <p className="muted">None: no other stock in this market passes the rejection rules.</p>
        ) : (
          <ul className="alternatives">
            {insight.alternatives.map((alt) => (
              <li key={alt.symbol}>
                <button type="button" className="link" onClick={() => onPick(alt.symbol)}>
                  {alt.symbol}
                </button>
                <ScoreMeter score={alt.score} compact />
              </li>
            ))}
          </ul>
        )}
        <p className="footnote">
          Highest scores among the other stocks in this market. "No trade" stays a valid choice,
          and the system never switches stocks for you.
        </p>
      </Section>

      <Section title={`How the current strategy did on ${symbol}`} aside={<BacktestTag />}>
        {history.summary.trades === 0 ? (
          <p className="muted">It made no completed trades in this stock in the stored history.</p>
        ) : (
          <>
            <p>
              {history.summary.trades} past trades, {pct(history.summary.win_rate)} winners,
              average {r(history.summary.expectancy_r)} per trade.{" "}
              {history.summary.trades < 30 && "Too few trades to draw a conclusion from."}
            </p>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th>Why it closed</th>
                    <th className="num">Sessions</th>
                    <th className="num">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {history.recent.map((t) => (
                    <tr key={`${t.entry_date}`}>
                      <td>{formatDate(t.entry_date)}</td>
                      <td>{t.exit_date ? formatDate(t.exit_date) : "still open"}</td>
                      <td>{t.reason}</td>
                      <td className="num">{t.holding_sessions}</td>
                      <td className={`num ${signClass(t.r_multiple)}`}>{r(t.r_multiple)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Section>

      {indicators.quality_issues.length > 0 && (
        <Section title="Data-quality warnings">
          <ul className="reasons">
            {indicators.quality_issues.slice(0, 8).map((issue, i) => (
              <li key={i}>
                {issue.kind.replaceAll("_", " ")}
                {issue.date ? `, ${formatDate(issue.date)}` : ""}: {issue.detail}
              </li>
            ))}
            {indicators.quality_issues.length > 8 && (
              <li>and {indicators.quality_issues.length - 8} more.</li>
            )}
          </ul>
        </Section>
      )}
    </>
  );
}
