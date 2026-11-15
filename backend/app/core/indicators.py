"""Technical indicators as pure functions (CONTEXT.md section 5).

Conventions
- Inputs are pandas Series ordered oldest to newest, one value per completed session.
- No look-ahead: the value at position i uses only positions <= i.
- Where there is not enough history the result is NaN ("insufficient data"), never a guess.
- Callers pass adjusted prices (see `adjust_ohlc`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


def adjust_ohlc(
    open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, adj_close: pd.Series
) -> pd.DataFrame:
    """Scale O/H/L by adj_close / close so the whole candle is split- and dividend-adjusted."""
    factor = adj_close / close
    return pd.DataFrame(
        {"open": open_ * factor, "high": high * factor, "low": low * factor, "close": adj_close}
    )


def sma(values: pd.Series, window: int) -> pd.Series:
    """Simple moving average of the last `window` values."""
    return values.rolling(window, min_periods=window).mean()


def _first_full_window(array: np.ndarray[Any, np.dtype[np.float64]], window: int) -> int | None:
    """Start index of the first run of `window` consecutive finite values."""
    run = 0
    for i, value in enumerate(array):
        run = run + 1 if math.isfinite(value) else 0
        if run == window:
            return i - window + 1
    return None


def _recursive_average(values: pd.Series, window: int, alpha: float) -> pd.Series:
    """Seed with the simple mean of the first `window` values, then
    avg[i] = avg[i-1] + alpha * (x[i] - avg[i-1])."""
    array = values.to_numpy(dtype=float)
    out = np.full(len(array), np.nan)
    start = _first_full_window(array, window)
    if start is None:
        return pd.Series(out, index=values.index)
    seed_at = start + window - 1
    out[seed_at] = array[start : seed_at + 1].mean()
    for i in range(seed_at + 1, len(array)):
        if not math.isfinite(array[i]):
            break
        out[i] = out[i - 1] + alpha * (array[i] - out[i - 1])
    return pd.Series(out, index=values.index)


def ema(values: pd.Series, window: int) -> pd.Series:
    """Exponential moving average, alpha = 2 / (window + 1), seeded with the SMA of the
    first `window` values."""
    return _recursive_average(values, window, 2.0 / (window + 1))


def wilder_average(values: pd.Series, period: int) -> pd.Series:
    """Wilder smoothing, alpha = 1 / period, seeded with the simple mean."""
    return _recursive_average(values, period, 1.0 / period)


def rsi(close: pd.Series, period: int) -> pd.Series:
    """Relative Strength Index with Wilder smoothing. First value at position `period`.
    RSI is 100 when there were no losses, and NaN when price did not move at all."""
    delta = close.diff()
    avg_gain = wilder_average(delta.clip(lower=0.0), period)
    avg_loss = wilder_average((-delta).clip(lower=0.0), period)
    gain = avg_gain.to_numpy(dtype=float)
    loss = avg_loss.to_numpy(dtype=float)
    out = np.full(len(close), np.nan)
    for i in range(len(close)):
        if not (math.isfinite(gain[i]) and math.isfinite(loss[i])):
            continue
        if loss[i] == 0.0:
            out[i] = 100.0 if gain[i] > 0.0 else np.nan
        else:
            out[i] = 100.0 - 100.0 / (1.0 + gain[i] / loss[i])
    return pd.Series(out, index=close.index)


def macd(close: pd.Series, fast: int, slow: int, signal: int) -> pd.DataFrame:
    """MACD line (EMA fast - EMA slow), signal line (EMA of the MACD line) and histogram."""
    line = ema(close, fast) - ema(close, slow)
    signal_line = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": signal_line, "histogram": line - signal_line})


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """max(high - low, |high - prev close|, |low - prev close|). NaN for the first candle."""
    previous = close.shift(1)
    ranges = pd.concat([high - low, (high - previous).abs(), (low - previous).abs()], axis=1)
    result = ranges.max(axis=1)
    result[previous.isna()] = np.nan
    return result


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """Average True Range with Wilder smoothing. First value at position `period`."""
    return wilder_average(true_range(high, low, close), period)


def bollinger(close: pd.Series, window: int, num_std: float) -> pd.DataFrame:
    """SMA +/- num_std population standard deviations (ddof = 0)."""
    middle = sma(close, window)
    deviation = close.rolling(window, min_periods=window).std(ddof=0)
    return pd.DataFrame(
        {
            "middle": middle,
            "upper": middle + num_std * deviation,
            "lower": middle - num_std * deviation,
        }
    )


def relative_volume(volume: pd.Series, window: int) -> pd.Series:
    """Volume divided by the average volume of the *previous* `window` sessions."""
    baseline = volume.shift(1).rolling(window, min_periods=window).mean()
    return volume / baseline.where(baseline > 0)


def session_return(close: pd.Series, sessions: int) -> pd.Series:
    """Fractional change over the last `sessions` sessions (0.05 = +5%)."""
    return close / close.shift(sessions) - 1.0


def relative_strength(close: pd.Series, benchmark_close: pd.Series, sessions: int) -> pd.Series:
    """Stock return minus benchmark return over `sessions` sessions, measured on the dates
    both series have. Positive = the stock outperformed its benchmark."""
    joined = pd.concat({"stock": close, "benchmark": benchmark_close}, axis=1, join="inner")
    excess = session_return(joined["stock"], sessions) - session_return(
        joined["benchmark"], sessions
    )
    return excess.reindex(close.index)


def volatility(close: pd.Series, window: int, trading_days_per_year: int) -> pd.Series:
    """Annualised volatility: sample standard deviation of the last `window` daily returns
    times sqrt(trading_days_per_year)."""
    daily = close.pct_change()
    return daily.rolling(window, min_periods=window).std(ddof=1) * math.sqrt(trading_days_per_year)


def drawdown(close: pd.Series) -> pd.Series:
    """Fractional distance below the highest close so far (0 at a new high, negative below)."""
    return close / close.cummax() - 1.0


def max_drawdown(close: pd.Series) -> float:
    """Deepest drawdown in the series (a negative fraction, or 0). NaN for an empty series."""
    if close.empty:
        return float("nan")
    return float(drawdown(close).min())


@dataclass(frozen=True)
class Pivot:
    position: int  # position of the swing candle in the input series
    kind: str  # "high" | "low"
    price: float
    confirmed_position: int  # position of the candle that confirmed it


def confirmed_pivots(high: pd.Series, low: pd.Series, window: int) -> list[Pivot]:
    """Swing highs and lows already confirmed by `window` later candles.

    A swing high at i has a high strictly above the `window` candles before it and at or
    above the `window` candles after it (mirrored for lows). A candle within `window` of
    the end of the series cannot be a pivot yet, which keeps this free of look-ahead.
    """
    highs = high.to_numpy(dtype=float)
    lows = low.to_numpy(dtype=float)
    pivots: list[Pivot] = []
    for i in range(window, len(highs) - window):
        before_h, after_h = highs[i - window : i], highs[i + 1 : i + window + 1]
        if highs[i] > before_h.max() and highs[i] >= after_h.max():
            pivots.append(Pivot(i, "high", float(highs[i]), i + window))
        before_l, after_l = lows[i - window : i], lows[i + 1 : i + window + 1]
        if lows[i] < before_l.min() and lows[i] <= after_l.min():
            pivots.append(Pivot(i, "low", float(lows[i]), i + window))
    return pivots


def support_resistance(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int,
    lookback: int,
    max_levels: int,
) -> tuple[list[Pivot], list[Pivot]]:
    """Nearest confirmed pivot prices below (support) and above (resistance) the last close,
    taken from the last `lookback` sessions. Each list is ordered nearest first."""
    if close.empty:
        return [], []
    last_close = float(close.iloc[-1])
    earliest = max(0, len(close) - lookback)
    pivots = [p for p in confirmed_pivots(high, low, window) if p.position >= earliest]
    support = sorted((p for p in pivots if p.price < last_close), key=lambda p: -p.price)
    resistance = sorted((p for p in pivots if p.price > last_close), key=lambda p: p.price)
    return support[:max_levels], resistance[:max_levels]


def beta(close: pd.Series, benchmark_close: pd.Series, sessions: int) -> tuple[float, float] | None:
    """(beta, correlation) of daily returns over the last `sessions` sessions both series
    share. None when there is not enough overlapping history or the benchmark is flat."""
    joined = pd.concat({"s": close, "b": benchmark_close}, axis=1, join="inner").pct_change()
    joined = joined.dropna().tail(sessions)
    if len(joined) < sessions:
        return None
    variance = float(joined["b"].var(ddof=1))
    if not math.isfinite(variance) or variance <= 0:
        return None
    covariance = float(joined["s"].cov(joined["b"]))
    correlation = float(joined["s"].corr(joined["b"]))
    return covariance / variance, correlation
