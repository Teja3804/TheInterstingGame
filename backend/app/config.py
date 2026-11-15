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


class Settings(BaseModel):
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

    database_url = os.environ.get("STI_DATABASE_URL")
    if database_url:
        raw.setdefault("database", {})["url"] = database_url
    origins = os.environ.get("STI_CORS_ORIGINS", "http://localhost:5173")
    raw["cors_origins"] = [o.strip() for o in origins.split(",") if o.strip()]
    return Settings.model_validate(raw)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
