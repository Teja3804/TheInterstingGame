import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type IndicatorsResponse, type Level } from "../api";
import { Price } from "../components/Price";
import { CHART_COLORS, PriceChart, type Overlays } from "../components/PriceChart";
import {
  formatDate,
  formatFraction,
  formatInstant,
  formatLocal,
  formatNumber,
  formatPercent,
  formatVolume,
  signClass,
} from "../format";
import { useLoad } from "../useLoad";

const SESSIONS = 520;

type Kind = "price" | "number" | "fraction" | "percent" | "level";

function rows(data: IndicatorsResponse): [string, string, Kind][] {
  const p = data.parameters;
  return [
    ...p.return_windows.map(
      (n): [string, string, Kind] => [`return_${n}`, `Return, ${n} session${n > 1 ? "s" : ""}`, "fraction"],
    ),
    ...p.sma_windows.map((n): [string, string, Kind] => [`sma_${n}`, `SMA ${n}`, "price"]),
    ...p.sma_windows.map(
      (n): [string, string, Kind] => [`pct_vs_sma_${n}`, `Close vs SMA ${n}`, "percent"],
    ),
    ...p.ema_windows.map((n): [string, string, Kind] => [`ema_${n}`, `EMA ${n}`, "price"]),
    ["rsi", `RSI ${p.rsi_period} (Wilder)`, "number"],
    ["macd", `MACD (${p.macd.fast}, ${p.macd.slow})`, "number"],
    ["macd_signal", `MACD signal (${p.macd.signal})`, "number"],
    ["macd_histogram", "MACD histogram", "number"],
    ["atr", `ATR ${p.atr_period} (Wilder)`, "price"],
    ["atr_pct", "ATR as % of close", "number"],
    ["bb_upper", `Bollinger upper (${p.bollinger.window}, ${p.bollinger.num_std}σ)`, "price"],
    ["bb_middle", "Bollinger middle", "price"],
    ["bb_lower", "Bollinger lower", "price"],
    ["relative_volume", `Volume vs previous ${p.relative_volume_window} sessions`, "number"],
    [
      "relative_strength",
      `Return minus ${data.relative_strength_benchmark ?? "benchmark"}, ${p.relative_strength_window} sessions`,
      "fraction",
    ],
    ["volatility", `Volatility, annualised (${p.volatility_window} sessions)`, "level"],
    ["drawdown", "Drawdown from highest stored close", "fraction"],
    ["max_drawdown", "Largest drawdown in stored history", "fraction"],
  ];
}

function show(value: number | null | undefined, kind: Kind): string {
  if (kind === "fraction") return formatFraction(value);
  if (kind === "percent") return formatPercent(value);
  // A magnitude, not a gain or loss: no sign and no colour.
  if (kind === "level") return value == null ? formatNumber(value) : `${formatNumber(value * 100)}%`;
  return formatNumber(value);
}

function Levels({ title, levels, currency }: { title: string; levels: Level[]; currency: string }) {
  return (
    <>
      <h3>{title}</h3>
      {levels.length === 0 ? (
        <p className="muted">None found in the lookback window.</p>
      ) : (
        <ul className="levels">
          {levels.map((level) => (
            <li key={`${level.pivot_date}-${level.kind}`}>
              <strong>
                {formatNumber(level.price)} {currency}
              </strong>{" "}
              {level.kind} on {formatDate(level.pivot_date)}, confirmed{" "}
              {formatDate(level.confirmed_date)}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

export function StockDetail() {
  const symbol = useParams().symbol ?? "";
  const prices = useLoad(() => api.prices(symbol, SESSIONS), `prices:${symbol}`);
  const indicators = useLoad(() => api.indicators(symbol, SESSIONS), `indicators:${symbol}`);
  const [overlays, setOverlays] = useState<Overlays>({
    sma: true,
    ema: false,
    bollinger: false,
    levels: true,
  });

  const error = prices.error ?? indicators.error;
  if (error) {
    return (
      <p className="notice notice-error">
        Could not load {symbol} ({error}). <Link to="/watchlist">Back to the watchlist</Link>
      </p>
    );
  }
  if (!prices.data || !indicators.data) return <p className="notice">Loading {symbol}…</p>;
  const data = indicators.data;
  const zone = data.timezone;
  const lastBar = prices.data.bars.at(-1);
  const toggle = (key: keyof Overlays) => setOverlays((o) => ({ ...o, [key]: !o[key] }));

  return (
    <>
      <p className="crumb">
        <Link to="/watchlist">Watchlist</Link> / {symbol}
      </p>
      <div className={`detail-head market market-${data.market}`}>
        <div>
          <h1>
            {symbol}
            {data.is_benchmark && <span className="tag">benchmark</span>}
          </h1>
          <p className="sub">{data.profile?.name ?? "Name unavailable"}</p>
        </div>
        <Price value={data.snapshot.last_close} from={data} size="large" />
      </div>

      {data.candle_date === null ? (
        <p className="notice notice-warn">
          No data is stored for {symbol}. Go to <Link to="/">Overview</Link> and choose “Refresh
          data now”.
        </p>
      ) : (
        <section className="panel">
          <div className="panel-head">
            <h2>Daily candles, adjusted for splits and dividends</h2>
            <fieldset className="toggles">
              <legend className="visually-hidden">Chart overlays</legend>
              {(
                [
                  ["sma", `SMA ${data.parameters.sma_windows.join(" / ")}`],
                  ["ema", `EMA ${data.parameters.ema_windows.join(" / ")}`],
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
          <PriceChart prices={prices.data} indicators={data} overlays={overlays} />
          <p className="footnote">
            Panels from top: price with volume, RSI {data.parameters.rsi_period} with 30 and 70
            guides, MACD. Colours:{" "}
            {data.parameters.sma_windows.map((w, i) => (
              <span key={w} className="key" style={{ borderColor: CHART_COLORS.sma[i % 3] }}>
                SMA {w}
              </span>
            ))}
            {data.parameters.ema_windows.map((w, i) => (
              <span key={w} className="key" style={{ borderColor: CHART_COLORS.ema[i % 2] }}>
                EMA {w}
              </span>
            ))}
            . Last session volume: {formatVolume(lastBar?.volume)}.
          </p>
        </section>
      )}

      <div className="detail-grid">
        <section className="panel">
          <h2>Indicator snapshot</h2>
          <dl className="facts facts-wide">
            <dt>Candle used</dt>
            <dd>
              {data.as_of_local ? formatLocal(data.as_of_local, zone) : formatDate(data.candle_date)}
            </dd>
            <dt>Data fetched</dt>
            <dd>{formatInstant(data.fetched_at_utc, zone)}</dd>
            <dt>Source</dt>
            <dd>{data.source_label}</dd>
          </dl>
          <table className="snapshot">
            <tbody>
              {rows(data).map(([field, label, kind]) => {
                const value = data.snapshot[field];
                const missing = value === null || value === undefined;
                return (
                  <tr key={field}>
                    <th scope="row">{label}</th>
                    <td
                      className={`num ${kind === "fraction" || kind === "percent" ? signClass(value) : ""}`}
                    >
                      {missing ? (
                        <span className="muted">
                          {data.unavailable[field] ?? "unavailable: no data stored"}
                        </span>
                      ) : (
                        <>
                          {show(value, kind)}
                          {kind === "price" && <span className="currency"> {data.currency}</span>}
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>

        <div>
          <section className="panel">
            <h2>Support and resistance</h2>
            <Levels title="Resistance, nearest first" levels={data.resistance} currency={data.currency} />
            <Levels title="Support, nearest first" levels={data.support} currency={data.currency} />
            <p className="footnote">
              Swing highs and lows on adjusted prices, counted only once later candles confirmed
              them.
            </p>
          </section>

          <section className="panel">
            <h2>Data-quality warnings</h2>
            {data.quality_issues.length === 0 ? (
              <p className="muted">
                {data.candle_date ? "None found at the last refresh." : "Nothing to check yet."}
              </p>
            ) : (
              <ul className="issues">
                {data.quality_issues.slice(0, 25).map((issue, i) => (
                  <li key={i}>
                    <strong>{issue.kind.replaceAll("_", " ")}</strong>
                    {issue.date ? `, ${formatDate(issue.date)}` : ""}: {issue.detail}
                  </li>
                ))}
                {data.quality_issues.length > 25 && (
                  <li>and {data.quality_issues.length - 25} more.</li>
                )}
              </ul>
            )}
          </section>

          <section className="panel">
            <h2>Profile</h2>
            {data.profile === null ? (
              <p className="muted">Unavailable: no profile has been fetched for {symbol}.</p>
            ) : (
              <dl className="facts facts-wide">
                <dt>Name</dt>
                <dd>{data.profile.name ?? "unavailable"}</dd>
                <dt>Sector</dt>
                <dd>{data.profile.sector ?? "unavailable from source"}</dd>
                <dt>Industry</dt>
                <dd>{data.profile.industry ?? "unavailable from source"}</dd>
                <dt>Exchange</dt>
                <dd>{data.profile.exchange ?? "unavailable"}</dd>
                <dt>Currency</dt>
                <dd>{data.profile.currency ?? "unavailable"}</dd>
                <dt>Fetched</dt>
                <dd>{formatInstant(data.profile.fetched_at_utc, zone)}</dd>
              </dl>
            )}
            {data.corporate_actions.length > 0 && (
              <>
                <h3>Splits and dividends in stored history</h3>
                <ul className="levels">
                  {data.corporate_actions.slice(0, 12).map((action) => (
                    <li key={`${action.date}-${action.type}`}>
                      {formatDate(action.date)}: {action.type}{" "}
                      {action.type === "split"
                        ? `${formatNumber(action.value, 2)} for 1`
                        : `${formatNumber(action.value, 4)} ${data.currency} per share`}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>
        </div>
      </div>
    </>
  );
}
