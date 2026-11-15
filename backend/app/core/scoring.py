"""Explainable opportunity score (CONTEXT.md section 7). Pure functions.

Every component is a series from 0 to 100 computed with data available at each day's close
(no look-ahead). The total is the weighted average of the components that are available;
an unavailable component is left out and the remaining weights are rescaled, which the
caller reports. A score is a ranking, not a probability.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.core import indicators as ind

COMPONENTS = ("trend", "relative_strength", "momentum", "volume", "sector", "reward_risk")


@dataclass(frozen=True)
class ScoreParams:
    weights: dict[str, float]
    slope_sessions: int
    rs_sessions: int
    rs_floor_pct: float
    rs_cap_pct: float
    momentum_return_sessions: int
    rsi_best: tuple[float, float]
    rsi_ok: tuple[float, float]
    volume_average_sessions: int
    volume_floor: float
    volume_cap: float
    sector_sessions: int
    sector_floor_pct: float
    sector_cap_pct: float
    rr_floor: float
    rr_cap: float
    stop_atr_multiple: float
    target_r_multiple: float
    pivot_window: int
    pivot_lookback: int


def scale(values: pd.Series, floor: float, cap: float) -> pd.Series:
    """Linear map floor -> 0, cap -> 100, clipped. NaN stays NaN."""
    return ((values - floor) / (cap - floor) * 100.0).clip(0.0, 100.0)


def _flag(condition: pd.Series, valid: pd.Series) -> pd.Series:
    """100 where true, 0 where false, NaN where the inputs are not available yet."""
    return condition.astype(float).where(valid) * 100.0


def trend_component(close: pd.Series, slope_sessions: int) -> pd.Series:
    """Average of four yes/no checks, 25 points each: close > SMA 50, close > SMA 200,
    SMA 50 > SMA 200, SMA 50 higher than `slope_sessions` sessions ago."""
    sma50, sma200 = ind.sma(close, 50), ind.sma(close, 200)
    past50 = sma50.shift(slope_sessions)
    valid = sma200.notna() & past50.notna()
    checks = [close > sma50, close > sma200, sma50 > sma200, sma50 > past50]
    return sum(_flag(c, valid) for c in checks) / len(checks)  # type: ignore[return-value]


def momentum_component(
    close: pd.Series,
    rsi: pd.Series,
    macd_histogram: pd.Series,
    return_sessions: int,
    rsi_best: tuple[float, float],
    rsi_ok: tuple[float, float],
) -> pd.Series:
    """Average of three parts: RSI band (100 / 50 / 0), MACD histogram above zero,
    and a positive return over `return_sessions`."""
    rsi_score = pd.Series(0.0, index=close.index)
    rsi_score[(rsi >= rsi_ok[0]) & (rsi <= rsi_ok[1])] = 50.0
    rsi_score[(rsi >= rsi_best[0]) & (rsi <= rsi_best[1])] = 100.0
    rsi_score = rsi_score.where(rsi.notna())
    past_return = ind.session_return(close, return_sessions)
    return (
        rsi_score
        + _flag(macd_histogram > 0, macd_histogram.notna())
        + _flag(past_return > 0, past_return.notna())
    ) / 3.0


def nearest_resistance(
    high: pd.Series, low: pd.Series, close: pd.Series, window: int, lookback: int
) -> pd.Series:
    """For each day, the lowest confirmed pivot price above that day's close, using only
    pivots confirmed on or before that day and no older than `lookback` sessions."""
    pivots = ind.confirmed_pivots(high, low, window)
    closes = close.to_numpy(dtype=float)
    out = np.full(len(closes), np.nan)
    for i in range(len(closes)):
        above = [
            p.price
            for p in pivots
            if p.confirmed_position <= i and p.position >= i - lookback and p.price > closes[i]
        ]
        if above:
            out[i] = min(above)
    return pd.Series(out, index=close.index)


def reward_risk_ratio(
    close: pd.Series, atr: pd.Series, resistance: pd.Series, params: ScoreParams
) -> pd.Series:
    """Room to the nearest resistance divided by the planned stop distance. With no
    resistance overhead, the planned target (target_r_multiple) is used instead."""
    risk = params.stop_atr_multiple * atr
    room = (resistance - close).where(resistance.notna(), params.target_r_multiple * risk)
    return (room / risk.where(risk > 0)).where(atr.notna())


def score_frame(
    adjusted: pd.DataFrame,
    volume: pd.Series,
    benchmark_close: pd.Series | None,
    sector_close: pd.Series | None,
    params: ScoreParams,
) -> pd.DataFrame:
    """Component scores, the weighted total and the inputs behind them, one row per day.

    `adjusted` has adjusted open/high/low/close indexed by date.
    """
    close, high, low = adjusted["close"], adjusted["high"], adjusted["low"]
    rsi = ind.rsi(close, 14)
    macd = ind.macd(close, 12, 26, 9)
    atr = ind.atr(high, low, close, 14)
    out = pd.DataFrame(index=close.index)

    out["trend"] = trend_component(close, params.slope_sessions)

    if benchmark_close is not None:
        excess = ind.relative_strength(close, benchmark_close, params.rs_sessions) * 100.0
        out["relative_strength"] = scale(excess, params.rs_floor_pct, params.rs_cap_pct)
        out["input_excess_return_pct"] = excess
    else:
        out["relative_strength"] = np.nan
        out["input_excess_return_pct"] = np.nan

    out["momentum"] = momentum_component(
        close,
        rsi,
        macd["histogram"],
        params.momentum_return_sessions,
        params.rsi_best,
        params.rsi_ok,
    )

    relative_volume = ind.relative_volume(volume, 20)
    average_rv = relative_volume.rolling(
        params.volume_average_sessions, min_periods=params.volume_average_sessions
    ).mean()
    out["volume"] = scale(average_rv, params.volume_floor, params.volume_cap)
    out["input_avg_relative_volume"] = average_rv

    if sector_close is not None and benchmark_close is not None:
        joined = pd.concat({"s": sector_close, "b": benchmark_close}, axis=1, join="inner")
        sector_excess = (
            ind.session_return(joined["s"], params.sector_sessions)
            - ind.session_return(joined["b"], params.sector_sessions)
        ).reindex(close.index) * 100.0
        out["sector"] = scale(sector_excess, params.sector_floor_pct, params.sector_cap_pct)
        out["input_sector_excess_pct"] = sector_excess
    else:
        out["sector"] = np.nan
        out["input_sector_excess_pct"] = np.nan

    resistance = nearest_resistance(high, low, close, params.pivot_window, params.pivot_lookback)
    ratio = reward_risk_ratio(close, atr, resistance, params)
    out["reward_risk"] = scale(ratio, params.rr_floor, params.rr_cap)
    out["input_reward_risk"] = ratio
    out["input_nearest_resistance"] = resistance

    weights = pd.Series({name: float(params.weights[name]) for name in COMPONENTS})
    parts = out[list(COMPONENTS)]
    used_weight = parts.notna().mul(weights, axis=1).sum(axis=1)
    weighted = parts.mul(weights, axis=1).sum(axis=1, min_count=1)
    # The three price-only components must exist before any total is reported.
    core_ready = parts[["trend", "momentum", "reward_risk"]].notna().all(axis=1)
    out["score"] = (weighted / used_weight.where(used_weight > 0)).where(core_ready)
    out["weight_used"] = used_weight.where(core_ready)

    out["input_rsi"] = rsi
    out["input_macd_histogram"] = macd["histogram"]
    out["input_atr"] = atr
    out["input_atr_pct"] = atr / close * 100.0
    out["input_sma_50"] = ind.sma(close, 50)
    out["input_sma_200"] = ind.sma(close, 200)
    out["input_return_pct"] = ind.session_return(close, params.momentum_return_sessions) * 100.0
    return out


def rejection_frame(
    adjusted: pd.DataFrame,
    raw_close: pd.Series,
    volume: pd.Series,
    atr_pct: pd.Series,
    min_sessions: int,
    min_avg_traded_value: float,
    max_atr_pct: float,
) -> pd.DataFrame:
    """Hard rejection flags per day (True = rejected for that reason)."""
    out = pd.DataFrame(index=adjusted.index)
    out["insufficient_history"] = np.arange(1, len(adjusted) + 1) < min_sessions
    traded = (raw_close * volume).rolling(20, min_periods=20).mean()
    out["insufficient_liquidity"] = ~(traded >= min_avg_traded_value)
    out["too_volatile"] = ~(atr_pct <= max_atr_pct)
    out["rejected"] = out.any(axis=1)
    out["input_avg_traded_value"] = traded
    return out
