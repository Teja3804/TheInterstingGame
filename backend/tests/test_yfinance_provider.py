"""YFinanceProvider behaviour with a fake ticker: no network is touched."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pandas as pd
import pytest

from app.config import Settings
from app.providers.base import ProviderError, RateLimitError, SymbolNotFoundError
from app.providers.yfinance_provider import YFinanceProvider


class YFRateLimitError(Exception):
    """Stands in for yfinance.exceptions.YFRateLimitError (matched by class name)."""


class YFTickerMissingError(Exception):
    pass


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class FakeTicker:
    def __init__(self, outcomes: list[Any], info: Any = None) -> None:
        self.outcomes = outcomes
        self.history_kwargs: list[dict[str, Any]] = []
        self._info = info

    def history(self, **kwargs: Any) -> Any:
        self.history_kwargs.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    @property
    def info(self) -> Any:
        if isinstance(self._info, Exception):
            raise self._info
        return self._info


def frame(hand: pd.DataFrame, tz: str = "America/New_York") -> pd.DataFrame:
    """The hand_calculated fixture shaped like a yfinance response."""
    index = pd.DatetimeIndex(pd.to_datetime(hand["date"])).tz_localize(tz)
    out = pd.DataFrame(
        {
            "Open": hand["open"].to_numpy(dtype=float),
            "High": hand["high"].to_numpy(dtype=float),
            "Low": hand["low"].to_numpy(dtype=float),
            "Close": hand["close"].to_numpy(dtype=float),
            "Adj Close": hand["adj_close"].to_numpy(dtype=float),
            "Volume": hand["volume"].to_numpy(dtype=float),
            "Dividends": 0.0,
            "Stock Splits": 0.0,
        },
        index=index,
    )
    out.iloc[2, out.columns.get_loc("Stock Splits")] = 2.0
    out.iloc[4, out.columns.get_loc("Dividends")] = 0.25
    return out


def make(settings: Settings, ticker: FakeTicker) -> tuple[YFinanceProvider, FakeClock]:
    clock = FakeClock()
    provider = YFinanceProvider(
        settings.provider,
        ticker_factory=lambda _: ticker,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )
    return provider, clock


START, END = dt.date(2024, 1, 1), dt.date(2024, 1, 9)


def test_parses_rows_actions_and_request_arguments(settings: Settings, hand: pd.DataFrame) -> None:
    ticker = FakeTicker([frame(hand)])
    provider, clock = make(settings, ticker)
    history = provider.fetch_daily_history("TEST", START, END)

    assert [b.date for b in history.bars] == hand["date"].tolist()
    assert history.bars[-1].close == 12.0 and history.bars[-1].volume == 900.0
    assert [(a.date, a.action_type, a.value) for a in history.actions] == [
        (dt.date(2024, 1, 3), "split", 2.0),
        (dt.date(2024, 1, 5), "dividend", 0.25),
    ]
    kwargs = ticker.history_kwargs[0]
    assert kwargs["auto_adjust"] is False and kwargs["interval"] == "1d"
    assert kwargs["start"] == "2024-01-01" and kwargs["end"] == "2024-01-10"  # end is exclusive
    assert clock.sleeps == []


def test_session_date_comes_from_exchange_local_time(
    settings: Settings, hand: pd.DataFrame
) -> None:
    # Midnight IST is the previous day in UTC; the session date must stay the local one.
    ticker = FakeTicker([frame(hand, tz="Asia/Kolkata")])
    provider, _ = make(settings, ticker)
    history = provider.fetch_daily_history("TEST.NS", START, END)
    assert history.bars[0].date == dt.date(2024, 1, 1)


def test_retries_with_exponential_backoff(settings: Settings, hand: pd.DataFrame) -> None:
    ticker = FakeTicker([ConnectionError("boom"), TimeoutError("slow"), frame(hand)])
    provider, clock = make(settings, ticker)
    history = provider.fetch_daily_history("TEST", START, END)
    assert len(history.bars) == 7
    base = settings.provider.backoff_base_seconds
    assert clock.sleeps == [base, base * 2]  # the backoff also satisfies the minimum delay


def test_gives_up_after_max_retries(settings: Settings) -> None:
    attempts = settings.provider.max_retries + 1
    ticker = FakeTicker([ConnectionError("boom")] * attempts)
    provider, clock = make(settings, ticker)
    with pytest.raises(ProviderError, match=f"failed after {attempts} attempts"):
        provider.fetch_daily_history("TEST", START, END)
    assert len(ticker.history_kwargs) == attempts
    assert len(clock.sleeps) == settings.provider.max_retries
    assert max(clock.sleeps) <= settings.provider.backoff_max_seconds


def test_rate_limit_adds_a_cooldown(settings: Settings, hand: pd.DataFrame) -> None:
    ticker = FakeTicker([YFRateLimitError("Too Many Requests"), frame(hand)])
    provider, clock = make(settings, ticker)
    provider.fetch_daily_history("TEST", START, END)
    cfg = settings.provider
    assert clock.sleeps == [cfg.backoff_base_seconds + cfg.rate_limit_cooldown_seconds]


def test_rate_limit_that_never_clears_raises_rate_limit_error(settings: Settings) -> None:
    ticker = FakeTicker(
        [YFRateLimitError("Too Many Requests")] * (settings.provider.max_retries + 1)
    )
    provider, _ = make(settings, ticker)
    with pytest.raises(RateLimitError):
        provider.fetch_daily_history("TEST", START, END)


def test_unknown_symbol_is_not_retried(settings: Settings) -> None:
    ticker = FakeTicker([YFTickerMissingError("possibly delisted")])
    provider, clock = make(settings, ticker)
    with pytest.raises(SymbolNotFoundError):
        provider.fetch_daily_history("NOPE", START, END)
    assert len(ticker.history_kwargs) == 1 and clock.sleeps == []


def test_real_yfinance_exception_classes_are_recognised() -> None:
    from yfinance import exceptions as yfe

    from app.providers.yfinance_provider import _classify

    assert _classify(yfe.YFRateLimitError()) is RateLimitError
    assert _classify(yfe.YFPricesMissingError("X", "")) is SymbolNotFoundError
    assert _classify(ValueError("x")) is ProviderError


def test_empty_response_means_symbol_not_found(settings: Settings) -> None:
    provider, _ = make(settings, FakeTicker([pd.DataFrame()]))
    with pytest.raises(SymbolNotFoundError, match="no rows"):
        provider.fetch_daily_history("NOPE", START, END)


def test_response_missing_columns_is_rejected(settings: Settings, hand: pd.DataFrame) -> None:
    provider, _ = make(settings, FakeTicker([frame(hand).drop(columns=["Adj Close"])]))
    with pytest.raises(ProviderError, match="missing columns"):
        provider.fetch_daily_history("TEST", START, END)


def test_minimum_delay_between_requests(settings: Settings, hand: pd.DataFrame) -> None:
    ticker = FakeTicker([frame(hand), frame(hand), frame(hand)])
    provider, clock = make(settings, ticker)
    provider.fetch_daily_history("A", START, END)
    provider.fetch_daily_history("B", START, END)  # immediately after: must wait
    assert clock.sleeps == [settings.provider.min_request_interval_seconds]
    clock.now += 60  # plenty of time has passed: no wait
    provider.fetch_daily_history("C", START, END)
    assert len(clock.sleeps) == 1


def test_profile_fields_and_missing_values(settings: Settings) -> None:
    info = {
        "longName": "Synthetic Corp",
        "sector": "Tech",
        "industry": " ",
        "currency": "USD",
        "fullExchangeName": "TestEx",
        "quoteType": "EQUITY",
    }
    provider, _ = make(settings, FakeTicker([], info=info))
    profile = provider.fetch_profile("TEST")
    assert (profile.name, profile.sector, profile.exchange, profile.currency) == (
        "Synthetic Corp",
        "Tech",
        "TestEx",
        "USD",
    )
    assert profile.industry is None  # blank is unknown, not an empty guess


class QuoteTicker(FakeTicker):
    def __init__(self, outcomes: list[Any], meta: Any) -> None:
        super().__init__(outcomes)
        self.meta = meta

    def get_history_metadata(self) -> Any:
        return self.meta


def test_quote_reads_price_time_currency_and_daily_closes(
    settings: Settings, hand: pd.DataFrame
) -> None:
    when = int(dt.datetime(2024, 1, 9, 20, 59, tzinfo=dt.UTC).timestamp())
    meta = {"regularMarketPrice": 12.34, "regularMarketTime": when, "currency": "USD"}
    ticker = QuoteTicker([frame(hand)], meta)
    provider, _ = make(settings, ticker)
    quote = provider.fetch_quote("TEST")

    assert quote.price == 12.34 and quote.currency == "USD"
    assert quote.market_time == dt.datetime(2024, 1, 9, 20, 59, tzinfo=dt.UTC)
    assert quote.daily_closes[-1] == (hand["date"].iloc[-1], 12.0)
    assert ticker.history_kwargs[0]["period"] == "5d"
    assert ticker.history_kwargs[0]["interval"] == "1d"


def test_quote_accepts_a_formatted_timestamp(settings: Settings, hand: pd.DataFrame) -> None:
    stamp = pd.Timestamp("2024-01-09 15:59", tz="America/New_York")
    ticker = QuoteTicker([frame(hand)], {"regularMarketPrice": 5, "regularMarketTime": stamp})
    quote = make(settings, ticker)[0].fetch_quote("TEST")
    assert quote.market_time == dt.datetime(2024, 1, 9, 20, 59, tzinfo=dt.UTC)
    assert quote.currency is None


@pytest.mark.parametrize(
    "meta",
    [
        {"regularMarketTime": 1704833940},
        {"regularMarketPrice": "12", "regularMarketTime": 1704833940},
        {"regularMarketPrice": 12.0},
        {"regularMarketPrice": 12.0, "regularMarketTime": True},
    ],
)
def test_quote_without_price_or_time_is_an_error(
    settings: Settings, hand: pd.DataFrame, meta: dict[str, Any]
) -> None:
    provider, _ = make(settings, QuoteTicker([frame(hand)], meta))
    with pytest.raises(ProviderError):
        provider.fetch_quote("TEST")
