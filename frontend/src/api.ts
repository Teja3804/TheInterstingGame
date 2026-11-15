// Types and fetch helpers for the backend API. The frontend only displays what the
// backend sends: no financial calculations happen here.

export type Freshness = "fresh" | "stale" | "missing" | "unknown";

export interface Scheduler {
  active: boolean;
  last_successful_run_utc: string | null;
  note: string;
}

export interface Clock {
  timezone: string;
  now_local: string;
  is_open: boolean;
  last_completed_session: string | null;
  last_completed_close_utc: string | null;
  next_session: string | null;
  calendar: string;
  calendar_valid_through: string;
  calendar_warning: string | null;
}

export interface SourceSymbol {
  symbol: string;
  market: string;
  is_benchmark: boolean;
  freshness: Freshness;
  first_candle_date: string | null;
  latest_candle_date: string | null;
  stored_rows: number;
  last_attempt_utc: string | null;
  last_success_utc: string | null;
  last_error_utc: string | null;
  last_error: string | null;
  last_outcome: string | null;
  last_rows_fetched: number | null;
  quality_issue_count: number;
}

export interface SourcesStatus {
  generated_at_utc: string;
  provider: {
    name: string;
    label: string;
    data_kind: string;
    last_success_utc: string | null;
    last_attempt_utc: string | null;
    symbols_failing: string[];
  };
  scheduler: Scheduler;
  markets: {
    code: string;
    name: string;
    currency: string;
    clock: Clock;
    freshness_counts: Record<Freshness, number>;
  }[];
  symbols: SourceSymbol[];
}

export interface Provenance {
  symbol: string;
  market: string;
  currency: string;
  timezone: string;
  source: string;
  source_label: string;
  last_completed_session: string | null;
  candle_date: string | null;
  as_of_local: string | null;
  fetched_at_utc: string | null;
  freshness: Freshness;
  sessions_stored: number;
  unavailable_reason?: string;
}

export type Values = Record<string, number | null | undefined>;

export interface WatchRow extends Provenance {
  is_benchmark: boolean;
  name: string | null;
  relative_strength_benchmark: string | null;
  values: Values;
  unavailable: Record<string, string>;
}

export interface WatchMarket {
  code: string;
  name: string;
  currency: string;
  timezone: string;
  relative_strength_benchmark: string;
  relative_strength_window: number;
  clock: Clock;
  rows: WatchRow[];
}

export interface Level {
  price: number;
  kind: string;
  pivot_date: string;
  confirmed_date: string;
}

export interface Bar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  adj_close: number;
  adj_open: number;
  adj_high: number;
  adj_low: number;
  volume: number;
  fetched_at_utc: string | null;
}

export interface PricesResponse extends Provenance {
  bars: Bar[];
  price_note?: string;
}

export interface IndicatorsResponse extends Provenance {
  is_benchmark: boolean;
  relative_strength_benchmark: string | null;
  parameters: {
    sma_windows: number[];
    ema_windows: number[];
    rsi_period: number;
    atr_period: number;
    relative_volume_window: number;
    relative_strength_window: number;
    volatility_window: number;
    return_windows: number[];
    macd: { fast: number; slow: number; signal: number };
    bollinger: { window: number; num_std: number };
  };
  profile: {
    name: string | null;
    sector: string | null;
    industry: string | null;
    exchange: string | null;
    currency: string | null;
    quote_type: string | null;
    source: string;
    fetched_at_utc: string | null;
  } | null;
  quality_issues: { kind: string; date: string | null; detail: string }[];
  corporate_actions: { date: string; type: string; value: number }[];
  snapshot: Values;
  unavailable: Record<string, string>;
  dates: string[];
  series: Record<string, (number | null)[]>;
  support: Level[];
  resistance: Level[];
}

export interface IngestResponse {
  fetched: number;
  cached: number;
  failed: number;
  results: { symbol: string; outcome: string; error: string | null }[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // not JSON: keep the status text
    }
    throw new Error(`${response.status}: ${detail}`);
  }
  return (await response.json()) as T;
}

const sym = (symbol: string) => encodeURIComponent(symbol);

export const api = {
  status: () => request<SourcesStatus>("/api/sources/status"),
  watchlists: () => request<{ markets: WatchMarket[] }>("/api/watchlists"),
  prices: (symbol: string, sessions: number) =>
    request<PricesResponse>(`/api/symbols/${sym(symbol)}/prices?sessions=${sessions}`),
  indicators: (symbol: string, sessions: number) =>
    request<IndicatorsResponse>(`/api/symbols/${sym(symbol)}/indicators?sessions=${sessions}`),
  ingest: () =>
    request<IngestResponse>("/api/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }),
};

// ---- Screens: stocks, risk analysis, strategy comparison -------------------------------

export interface Suggestion {
  action: string;
  reasons: string[];
}

export interface Regime {
  label: string;
  benchmark: string;
  as_of: string | null;
  evidence: string[];
  rule?: string;
}

export interface StockRow extends Provenance {
  name: string | null;
  sector: string | null;
  score: number | null;
  suggestion: Suggestion;
  values: Values;
  spark?: (number | null)[];
}

export interface StocksMarket {
  code: string;
  name: string;
  currency: string;
  timezone: string;
  last_completed_session: string | null;
  regime: Regime;
  rows: StockRow[];
}

export interface StocksResponse {
  generated_at_utc: string;
  thresholds: { buy_candidate: number; watch: number; exit_below: number };
  note: string;
  markets: StocksMarket[];
}

export interface Summary {
  trades: number;
  wins: number;
  win_rate: number | null;
  win_rate_low: number | null;
  win_rate_high: number | null;
  avg_win_r: number | null;
  avg_loss_r: number | null;
  expectancy_r: number | null;
  profit_factor: number | null;
  total_r: number;
  total_return_pct: number;
  max_drawdown_pct: number;
  avg_holding_sessions: number | null;
  avg_cost_pct: number | null;
  worst_r: number | null;
  best_r: number | null;
  longest_losing_streak: number;
  gap_stops: number;
  worst_gap_r: number | null;
  exit_reasons: Record<string, number>;
}

export interface TradeRow {
  symbol: string;
  entry_date: string | null;
  exit_date: string | null;
  reason: string;
  holding_sessions: number;
  r_multiple: number | null;
  return_pct: number | null;
}

export interface Insight {
  available: boolean;
  reason?: string;
  label_note: string;
  regime: Regime;
  suggestion: Suggestion;
  score: number | null;
  weight_used: number | null;
  components: {
    key: string;
    label: string;
    formula: string;
    weight: number;
    score: number | null;
    unavailable_reason: string | null;
    inputs: { label: string; value: number | null; kind: "price" | "pct" | "number" }[];
  }[];
  rejections: string[];
  not_checked: string[];
  bullish: string[];
  bearish: string[];
  plan: {
    entry_reference: number;
    entry_condition: string;
    stop: number;
    stop_rule: string;
    target: number;
    target_rule: string;
    risk_per_share: number;
    risk_pct_of_price: number;
    reward_risk_after_costs: number;
    estimated_round_trip_cost_pct: number;
    max_holding_sessions: number;
    sizing: {
      example_equity: number;
      shares: number;
      binding_constraint: string;
      position_value: number;
      risk_amount: number;
      risk_budget: number;
      gap_loss_amount: number;
      gap_r_multiple: number;
      note: string;
    };
    scenarios: { name: string; text: string; changes_the_plan: string }[];
  } | null;
  if_held: {
    action: string;
    reasons: string[];
    trailing_stop: number | null;
    sma_50: number | null;
    max_holding_sessions: number;
    options: string[];
  };
  hedge: {
    instrument: string | null;
    benchmark: string;
    beta_sessions: number;
    beta: number | null;
    correlation?: number;
    variance_explained_pct?: number;
    hedge_value_per_100?: number;
    instrument_last_close?: number | null;
    unavailable_reason?: string;
    limitations: string[];
  };
  alternatives: { symbol: string; score: number }[];
  backtest_history: { label: string; strategy: string; summary: Summary; recent: TradeRow[] };
}

export interface SymbolBundle {
  prices: PricesResponse;
  indicators: IndicatorsResponse;
  insight: Insight;
}

export type Probability =
  | { available: false; reason: string }
  | {
      available: true;
      sample_trades: number;
      horizon_trades: number;
      paths: number;
      prob_profit: number;
      prob_drawdown: number;
      drawdown_threshold_pct: number;
      prob_losing_streak: number;
      losing_streak: number;
      return_p05_pct: number;
      return_p50_pct: number;
      return_p95_pct: number;
      worst_drawdown_p95_pct: number;
    };

export interface Portfolio {
  max_positions: number;
  trades_taken: number;
  signals_skipped: number;
  total_return_pct: number;
  max_drawdown_pct: number;
  note: string;
}

export type CurvePoint = { date: string; return_pct: number };
export type Bucket = Summary & { name: string };

export interface ExecutionNote {
  fills: string;
  stop: string;
  target: string;
  time_exit: string;
  costs: Record<string, { cost_bps_per_side: number; slippage_bps: number }>;
  risk_per_trade_pct: number;
  r_definition: string;
}

export interface RiskMarket {
  code: string;
  name: string;
  currency: string;
  period: { from: string | null; to: string | null };
  symbols_tested: number;
  summary: Summary;
  probability: Probability;
  by_volatility: Bucket[];
  by_regime: Bucket[];
  by_period: Bucket[];
  stress: {
    name: string;
    expectancy_r: number | null;
    win_rate: number | null;
    total_return_pct: number;
    max_drawdown_pct: number;
  }[];
  loss_limits: {
    risk_per_trade_pct: number;
    max_open_risk_pct: number;
    max_simultaneous_trades_at_full_risk: number;
    worst_tested_trade_r: number | null;
    worst_tested_trade_pct_of_equity: number | null;
    hypothetical_gap_r: number;
    all_open_trades_gap_pct_of_equity: number;
  };
  findings: string[];
  portfolio: Portfolio;
  equity_curve: CurvePoint[];
  open_trades: TradeRow[];
}

export interface RiskResponse {
  label: string;
  strategy: { name: string; rule: string };
  execution: ExecutionNote;
  warnings: string[];
  markets: RiskMarket[];
}

export interface StrategyRow {
  key: string;
  name: string;
  rule: string;
  is_current: boolean;
  summary: Summary;
  probability: Probability;
  portfolio: Portfolio;
  equity_curve: CurvePoint[];
  signals_now: string[];
  in_trade_now: string[];
  expectancy_vs_current_r: number | null;
}

export interface StrategiesResponse {
  label: string;
  execution: ExecutionNote;
  warnings: string[];
  markets: {
    code: string;
    name: string;
    period: { from: string | null; to: string | null };
    symbols_tested: number;
    as_of: string | null;
    benchmark: { symbol: string; buy_and_hold_return_pct: number | null; note: string };
    strategies: StrategyRow[];
  }[];
}

/** A hosted snapshot build reads exported JSON files instead of calling the backend. */
export const SNAPSHOT = import.meta.env.VITE_STATIC === "1";

const safeName = (symbol: string) => symbol.replace(/[^A-Za-z0-9.-]/g, "_");
const SESSIONS = 260;

export const screens = {
  status: () =>
    request<SourcesStatus & { snapshot?: { exported_at_utc: string; note: string } }>(
      SNAPSHOT ? "./data/status.json" : "/api/sources/status",
    ),
  stocks: () => request<StocksResponse>(SNAPSHOT ? "./data/stocks.json" : "/api/stocks"),
  risk: () => request<RiskResponse>(SNAPSHOT ? "./data/risk.json" : "/api/risk"),
  strategies: () =>
    request<StrategiesResponse>(SNAPSHOT ? "./data/strategies.json" : "/api/strategies"),
  symbol: async (symbol: string): Promise<SymbolBundle> => {
    if (SNAPSHOT) return request<SymbolBundle>(`./data/symbols/${safeName(symbol)}.json`);
    const [prices, indicators, insight] = await Promise.all([
      api.prices(symbol, SESSIONS),
      api.indicators(symbol, SESSIONS),
      request<Insight>(`/api/symbols/${sym(symbol)}/insight`),
    ]);
    return { prices, indicators, insight };
  },
};
