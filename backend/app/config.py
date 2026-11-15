"""Loads config/*.yaml plus environment overrides. No tunable values live in code."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]


class MarketConfig(BaseModel):
    name: str
    timezone: str
    currency: str
    calendar: str
    relative_strength_benchmark: str
    symbols: list[str]
    benchmarks: list[str]
    hedge_instrument: str | None = None
    extra_symbols: list[str] = Field(default_factory=list)
    sector_references: dict[str, str] = Field(default_factory=dict)

    def every_symbol(self) -> list[str]:
        """Benchmarks, sector references and extras first, then the watchlist; no repeats."""
        ordered = [
            *self.benchmarks,
            *self.extra_symbols,
            *self.sector_references.values(),
            *self.symbols,
        ]
        return list(dict.fromkeys(ordered))


class DatabaseConfig(BaseModel):
    url: str


class ProviderConfig(BaseModel):
    name: str
    label: str
    history_years: int = Field(ge=2)
    min_request_interval_seconds: float = Field(ge=0)
    max_retries: int = Field(ge=0)
    backoff_base_seconds: float = Field(gt=0)
    backoff_max_seconds: float = Field(gt=0)
    rate_limit_cooldown_seconds: float = Field(ge=0)
    cache_ttl_minutes: float = Field(ge=0)
    incremental_overlap_days: int = Field(ge=1)
    profile_ttl_days: float = Field(ge=0)


class SessionsConfig(BaseModel):
    close_buffer_minutes: int = Field(ge=0)
    calendar_end_warning_days: int = Field(ge=0)


class DataQualityConfig(BaseModel):
    suspicious_move_pct: float = Field(gt=0)
    missing_session_lookback_days: int = Field(gt=0)


class MacdConfig(BaseModel):
    fast: int
    slow: int
    signal: int


class BollingerConfig(BaseModel):
    window: int
    num_std: float


class SupportResistanceConfig(BaseModel):
    pivot_window: int = Field(ge=1)
    lookback_sessions: int = Field(ge=10)
    max_levels: int = Field(ge=1)


class IndicatorConfig(BaseModel):
    sma_windows: list[int]
    ema_windows: list[int]
    rsi_period: int
    macd: MacdConfig
    atr_period: int
    bollinger: BollingerConfig
    relative_volume_window: int
    return_windows: list[int]
    relative_strength_window: int
    volatility_window: int
    trading_days_per_year: int
    support_resistance: SupportResistanceConfig


class ApiConfig(BaseModel):
    default_price_sessions: int = Field(gt=0)
    max_price_sessions: int = Field(gt=0)


class ScoreThresholds(BaseModel):
    buy_candidate: float
    watch: float
    exit_below: float


class RejectionConfig(BaseModel):
    min_sessions: int
    min_avg_traded_value: dict[str, float]
    max_atr_pct: float


class RegimeConfig(BaseModel):
    high_volatility_percentile: float
    volatility_lookback_sessions: int


class ScoringConfig(BaseModel):
    weights: dict[str, float]
    components: dict[str, dict[str, Any]]
    thresholds: ScoreThresholds
    rejections: RejectionConfig
    regime: RegimeConfig


class RiskLimits(BaseModel):
    risk_per_trade_pct: float = Field(gt=0)
    max_open_risk_pct: float = Field(gt=0)
    max_stock_pct: float = Field(gt=0)
    max_sector_pct: float = Field(gt=0)


class PortfolioConfig(BaseModel):
    equity: float = Field(gt=0)
    cash: float = Field(ge=0)
    lot_size: int = Field(ge=1)


class PlanConfig(BaseModel):
    stop_atr_multiple: float = Field(gt=0)
    target_r_multiple: float = Field(gt=0)
    max_holding_sessions: int = Field(gt=0)
    trailing_lookback_sessions: int = Field(gt=0)
    trailing_atr_multiple: float = Field(gt=0)


class CostConfig(BaseModel):
    cost_bps_per_side: float = Field(ge=0)
    slippage_bps: float = Field(ge=0)


class StressConfig(BaseModel):
    extra_cost_bps_per_side: float
    stop_slippage_atr: float
    gap_r_multiple: float


class AnalysisConfig(BaseModel):
    min_trades_for_probability: int
    bootstrap_paths: int
    bootstrap_horizon_trades: int
    bootstrap_seed: int
    drawdown_alert_pct: float
    losing_streak: int
    stress: StressConfig


class HedgeConfig(BaseModel):
    beta_sessions: int


class RiskConfig(BaseModel):
    limits: RiskLimits
    portfolio: dict[str, PortfolioConfig]
    plan: PlanConfig
    hedge: HedgeConfig
    costs: dict[str, CostConfig]
    analysis: AnalysisConfig


class Settings(BaseModel):
    scoring: ScoringConfig
    risk: RiskConfig
    database: DatabaseConfig
    provider: ProviderConfig
    sessions: SessionsConfig
    data_quality: DataQualityConfig
    indicators: IndicatorConfig
    api: ApiConfig
    markets: dict[str, MarketConfig]
    cors_origins: list[str]

    def market_of(self, symbol: str) -> str | None:
        """Market code a configured symbol belongs to, or None if it is not configured."""
        for code, market in self.markets.items():
            if symbol in market.every_symbol():
                return code
        return None

    def is_benchmark(self, symbol: str) -> bool:
        return any(symbol in m.benchmarks for m in self.markets.values())

    def all_symbols(self) -> list[tuple[str, str]]:
        """(market, symbol) for everything that gets fetched, reference symbols first."""
        return [
            (code, symbol)
            for code, market in self.markets.items()
            for symbol in market.every_symbol()
        ]


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def load_settings(config_dir: Path | None = None) -> Settings:
    directory = config_dir or Path(os.environ.get("STI_CONFIG_DIR", REPO_ROOT / "config"))
    raw = _read_yaml(directory / "settings.yaml")
    raw["markets"] = _read_yaml(directory / "watchlists.yaml").get("markets", {})
    raw["scoring"] = _read_yaml(directory / "scoring.yaml")
    raw["risk"] = _read_yaml(directory / "risk.yaml")

    database_url = os.environ.get("STI_DATABASE_URL")
    if database_url:
        raw.setdefault("database", {})["url"] = database_url
    origins = os.environ.get("STI_CORS_ORIGINS", "http://localhost:5173")
    raw["cors_origins"] = [o.strip() for o in origins.split(",") if o.strip()]
    return Settings.model_validate(raw)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
