"""Entry and exit rules for the strategies compared on the Strategies screen. Pure.

Each function returns (entries, exits): booleans known at each day's close. The shared
simulator in app.core.backtest adds the stop, the target, the time limit, costs and
next-open fills, so every strategy is tested under identical execution.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from app.core import indicators as ind

Signals = tuple[pd.Series, pd.Series]


def _crosses_above(left: pd.Series, right: pd.Series) -> pd.Series:
    return (left > right) & (left.shift(1) <= right.shift(1))


def score_model(score: pd.Series, rejected: pd.Series, buy: float, exit_below: float) -> Signals:
    """Baseline: enter when the opportunity score is at or above the buy threshold with no
    hard rejection; signal an exit when the score falls below the exit threshold."""
    return (score >= buy) & ~rejected.astype(bool), score < exit_below


def sma_trend(close: pd.Series, window: int) -> Signals:
    """Enter when the close crosses above its SMA; exit when the close is below it."""
    average = ind.sma(close, window)
    return _crosses_above(close, average), close < average


def dip_in_uptrend(close: pd.Series, enter_below: float = 10.0, exit_window: int = 5) -> Signals:
    """Buy a short, sharp dip inside a long-term uptrend: close above SMA 200 and the
    2-session RSI below the entry level; exit when the close is back above its
    `exit_window`-session average."""
    quick_rsi = ind.rsi(close, 2)
    return (close > ind.sma(close, 200)) & (quick_rsi < enter_below), close > ind.sma(
        close, exit_window
    )


def breakout(
    high: pd.Series, low: pd.Series, close: pd.Series, enter: int = 20, leave: int = 10
) -> Signals:
    """Enter on a close above the highest high of the previous `enter` sessions; exit on a
    close below the lowest low of the previous `leave` sessions."""
    prior_high = high.shift(1).rolling(enter, min_periods=enter).max()
    prior_low = low.shift(1).rolling(leave, min_periods=leave).min()
    return close > prior_high, close < prior_low


def macd_cross(close: pd.Series) -> Signals:
    """Enter when the MACD histogram turns positive; exit when it is negative."""
    histogram = ind.macd(close, 12, 26, 9)["histogram"]
    zero = pd.Series(0.0, index=close.index)
    return _crosses_above(histogram, zero), histogram < 0


@dataclass(frozen=True)
class StrategySpec:
    key: str
    name: str
    rule: str
    build: Callable[[pd.DataFrame], Signals]  # frame: adjusted OHLC + score + rejected
    baseline: bool = False


def catalogue(buy_threshold: float, exit_below: float) -> list[StrategySpec]:
    return [
        StrategySpec(
            "score_model",
            "Scoring model (current)",
            f"Buy when the opportunity score is {buy_threshold:g} or higher with no hard "
            f"rejection. Exit signal when the score drops below {exit_below:g}.",
            lambda f: score_model(f["score"], f["rejected"], buy_threshold, exit_below),
            baseline=True,
        ),
        StrategySpec(
            "sma10_trend",
            "10-day average trend",
            "Buy when the close crosses above its 10-day average. Exit when it closes below.",
            lambda f: sma_trend(f["close"], 10),
        ),
        StrategySpec(
            "sma20_trend",
            "20-day average trend",
            "Buy when the close crosses above its 20-day average. Exit when it closes below.",
            lambda f: sma_trend(f["close"], 20),
        ),
        StrategySpec(
            "dip_in_uptrend",
            "Dip in an uptrend",
            "Buy when the close is above SMA 200 and the 2-session RSI is below 10. Exit when "
            "the close is back above its 5-session average.",
            lambda f: dip_in_uptrend(f["close"]),
        ),
        StrategySpec(
            "breakout_20",
            "20-day breakout",
            "Buy on a close above the previous 20-session high. Exit on a close below the "
            "previous 10-session low.",
            lambda f: breakout(f["high"], f["low"], f["close"]),
        ),
        StrategySpec(
            "macd_cross",
            "MACD turn",
            "Buy when the MACD histogram turns positive. Exit when it is negative.",
            lambda f: macd_cross(f["close"]),
        ),
    ]
