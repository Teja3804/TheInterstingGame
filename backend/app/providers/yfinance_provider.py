"""yfinance provider: unofficial, free, delayed / end-of-day. Never real-time."""

from __future__ import annotations

import datetime as dt
import logging
import math
import time
from collections.abc import Callable
from typing import Any, TypeVar

import pandas as pd

from app.config import ProviderConfig
from app.providers.base import (
    MarketDataProvider,
    PriceHistory,
    Profile,
    ProviderError,
    RateLimitError,
    RawAction,
    RawBar,
    SymbolNotFoundError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

REQUIRED_COLUMNS = ("Open", "High", "Low", "Close", "Adj Close", "Volume")


def _default_ticker_factory(symbol: str) -> Any:
    import yfinance as yf

    return yf.Ticker(symbol)


def _classify(exc: Exception) -> type[ProviderError]:
    """Map a yfinance exception to our error types without importing yfinance at module load."""
    names = {cls.__name__ for cls in type(exc).__mro__}
    if "YFRateLimitError" in names or "Too Many Requests" in str(exc):
        return RateLimitError
    if "YFTickerMissingError" in names:
        return SymbolNotFoundError
    return ProviderError


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


class YFinanceProvider(MarketDataProvider):
    name = "yfinance"

    def __init__(
        self,
        config: ProviderConfig,
        ticker_factory: Callable[[str], Any] = _default_ticker_factory,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._ticker_factory = ticker_factory
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_request_at: float | None = None

    # -- request pacing and retries -------------------------------------------------

    def _throttle(self) -> None:
        """Enforce the minimum delay between any two provider requests."""
        if self._last_request_at is not None:
            wait = self._config.min_request_interval_seconds - (
                self._monotonic() - self._last_request_at
            )
            if wait > 0:
                self._sleep(wait)
        self._last_request_at = self._monotonic()

    def _backoff_delay(self, attempt: int, rate_limited: bool) -> float:
        delay = min(
            self._config.backoff_base_seconds * (2.0**attempt), self._config.backoff_max_seconds
        )
        if rate_limited:
            delay += self._config.rate_limit_cooldown_seconds
        return delay

    def _with_retry(self, symbol: str, what: str, call: Callable[[], T]) -> T:
        last_error: Exception | None = None
        last_kind: type[ProviderError] = ProviderError
        for attempt in range(self._config.max_retries + 1):
            self._throttle()
            try:
                return call()
            except ProviderError:
                raise
            except Exception as exc:  # yfinance raises many unrelated types
                kind = _classify(exc)
                if kind is SymbolNotFoundError:
                    raise SymbolNotFoundError(f"{symbol}: no data from yfinance ({exc})") from exc
                last_error, last_kind = exc, kind
                if attempt < self._config.max_retries:
                    delay = self._backoff_delay(attempt, kind is RateLimitError)
                    logger.warning(
                        "yfinance %s for %s failed (attempt %d/%d): %s; retrying in %.1fs",
                        what,
                        symbol,
                        attempt + 1,
                        self._config.max_retries + 1,
                        type(exc).__name__,
                        delay,
                    )
                    self._sleep(delay)
        raise last_kind(
            f"{symbol}: yfinance {what} failed after {self._config.max_retries + 1} attempts "
            f"({type(last_error).__name__}: {last_error})"
        )

    # -- interface -------------------------------------------------------------------

    def fetch_daily_history(self, symbol: str, start: dt.date, end: dt.date) -> PriceHistory:
        def call() -> pd.DataFrame:
            frame = self._ticker_factory(symbol).history(
                start=start.isoformat(),
                end=(end + dt.timedelta(days=1)).isoformat(),  # yfinance `end` is exclusive
                interval="1d",
                auto_adjust=False,
                actions=True,
                raise_errors=True,
            )
            if not isinstance(frame, pd.DataFrame):
                raise ProviderError(f"{symbol}: yfinance returned {type(frame).__name__}")
            return frame

        frame = self._with_retry(symbol, "history", call)
        return self._parse_history(symbol, frame)

    def fetch_profile(self, symbol: str) -> Profile:
        def call() -> dict[str, Any]:
            info = self._ticker_factory(symbol).info
            if not isinstance(info, dict):
                raise ProviderError(f"{symbol}: yfinance returned no profile")
            return info

        info = self._with_retry(symbol, "profile", call)
        return Profile(
            symbol=symbol,
            name=_text(info.get("longName")) or _text(info.get("shortName")),
            sector=_text(info.get("sector")),
            industry=_text(info.get("industry")),
            exchange=_text(info.get("fullExchangeName")) or _text(info.get("exchange")),
            currency=_text(info.get("currency")),
            quote_type=_text(info.get("quoteType")),
        )

    # -- parsing -----------------------------------------------------------------------

    @staticmethod
    def _parse_history(symbol: str, frame: pd.DataFrame) -> PriceHistory:
        if frame.empty:
            raise SymbolNotFoundError(f"{symbol}: yfinance returned no rows")
        missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
        if missing:
            raise ProviderError(f"{symbol}: yfinance response is missing columns {missing}")
        if not isinstance(frame.index, pd.DatetimeIndex):
            raise ProviderError(f"{symbol}: yfinance response has no date index")

        bars: list[RawBar] = []
        actions: list[RawAction] = []
        # The index is in the exchange's local time zone, so .date() is the session date.
        for stamp, row in frame.iterrows():
            day = pd.Timestamp(stamp).date()  # type: ignore[arg-type]
            bars.append(
                RawBar(
                    date=day,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    adj_close=float(row["Adj Close"]),
                    volume=float(row["Volume"]),
                )
            )
            split = float(row["Stock Splits"]) if "Stock Splits" in frame.columns else 0.0
            dividend = float(row["Dividends"]) if "Dividends" in frame.columns else 0.0
            if math.isfinite(split) and split > 0:
                actions.append(RawAction(date=day, action_type="split", value=split))
            if math.isfinite(dividend) and dividend > 0:
                actions.append(RawAction(date=day, action_type="dividend", value=dividend))
        return PriceHistory(symbol=symbol, bars=bars, actions=actions)
