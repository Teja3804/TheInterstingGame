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
