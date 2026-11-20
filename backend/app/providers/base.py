"""Provider interface. Business logic depends only on this module, never on yfinance."""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RawBar:
    """One daily candle exactly as a provider returned it (not yet validated)."""

    date: dt.date
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: float


@dataclass(frozen=True)
class RawAction:
    date: dt.date
    action_type: str  # "split" | "dividend"
    value: float


@dataclass(frozen=True)
class PriceHistory:
    symbol: str
    bars: list[RawBar]
    actions: list[RawAction] = field(default_factory=list)


@dataclass(frozen=True)
class Profile:
    symbol: str
    name: str | None
    sector: str | None
    industry: str | None
    exchange: str | None
    currency: str | None
    quote_type: str | None


@dataclass(frozen=True)
class RawQuote:
    """Latest price exactly as a provider returned it (not yet validated).

    `market_time` is the provider's time for that price, timezone-aware. `daily_closes` are
    the provider's recent daily closes (session date, close), used to find the previous close.
    """

    symbol: str
    price: float
    market_time: dt.datetime
    currency: str | None
    daily_closes: list[tuple[dt.date, float]] = field(default_factory=list)


class ProviderError(Exception):
    """The provider failed after all retries, or returned an unusable response."""


class RateLimitError(ProviderError):
    """The provider reported rate limiting."""


class SymbolNotFoundError(ProviderError):
    """The provider has no data for this symbol (delisted, wrong suffix, ...)."""


class MarketDataProvider(ABC):
    """A source of daily candles, corporate actions and basic profiles."""

    name: str

    @abstractmethod
    def fetch_daily_history(self, symbol: str, start: dt.date, end: dt.date) -> PriceHistory:
        """Daily candles and corporate actions for start..end inclusive.

        May include an in-progress candle for the current session; callers must drop it.
        """

    @abstractmethod
    def fetch_profile(self, symbol: str) -> Profile:
        """Name, sector, industry, exchange and currency. Unknown fields are None."""

    @abstractmethod
    def fetch_quote(self, symbol: str) -> RawQuote:
        """Latest (delayed) price with the provider's own time for it."""
