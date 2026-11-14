"""Shared test doubles. All prices come from the synthetic fixture CSVs."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import pandas as pd

from app.config import Settings
from app.providers.base import (
    MarketDataProvider,
    PriceHistory,
    Profile,
    ProviderError,
    RawAction,
    RawBar,
)
from app.services.calendars import MarketCalendar

UTC = dt.UTC


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> dt.datetime:
    return dt.datetime(year, month, day, hour, minute, tzinfo=UTC)


def calendar_for(settings: Settings, market: str) -> MarketCalendar:
    return MarketCalendar(market, settings.markets[market], settings.sessions)


def bars_on_sessions(frame: pd.DataFrame, sessions: list[dt.date]) -> list[RawBar]:
    """Lay the last len(sessions) fixture rows onto real calendar session dates."""
    assert len(frame) >= len(sessions), "fixture too short for the requested window"
    rows = frame.tail(len(sessions)).reset_index(drop=True)
    return [
        RawBar(
            date=day,
            open=float(rows.at[i, "open"]),
            high=float(rows.at[i, "high"]),
            low=float(rows.at[i, "low"]),
            close=float(rows.at[i, "close"]),
            adj_close=float(rows.at[i, "adj_close"]),
            volume=float(rows.at[i, "volume"]),
        )
        for i, day in enumerate(sessions)
    ]


@dataclass
class FakeProvider(MarketDataProvider):
    """In-memory provider. Returns whatever bars it holds inside the requested range."""

    bars: dict[str, list[RawBar]] = field(default_factory=dict)
    actions: dict[str, list[RawAction]] = field(default_factory=dict)
    failing: dict[str, ProviderError] = field(default_factory=dict)
    calls: list[tuple[str, dt.date, dt.date]] = field(default_factory=list)
    profile_calls: list[str] = field(default_factory=list)
    name: str = "fake"

    def fetch_daily_history(self, symbol: str, start: dt.date, end: dt.date) -> PriceHistory:
        self.calls.append((symbol, start, end))
        if symbol in self.failing:
            raise self.failing[symbol]
        # Like yfinance, this may hand back today's in-progress candle: no upper clamp.
        bars = [b for b in self.bars.get(symbol, []) if b.date >= start]
        actions = [a for a in self.actions.get(symbol, []) if a.date >= start]
        return PriceHistory(symbol, bars, actions)

    def fetch_profile(self, symbol: str) -> Profile:
        self.profile_calls.append(symbol)
        return Profile(
            symbol, f"Synthetic {symbol}", "Test Sector", "Test Industry", "TEST", None, None
        )
