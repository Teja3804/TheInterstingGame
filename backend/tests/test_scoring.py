from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.core import advice, regime, scoring, strategies
from app.core import indicators as ind

PARAMS = scoring.ScoreParams(
    weights={
        "trend": 25,
        "relative_strength": 20,
        "momentum": 20,
        "volume": 15,
        "sector": 10,
        "reward_risk": 10,
    },
    slope_sessions=20,
    rs_sessions=20,
    rs_floor_pct=-10,
    rs_cap_pct=10,
    momentum_return_sessions=20,
    rsi_best=(50, 70),
    rsi_ok=(40, 80),
    volume_average_sessions=5,
    volume_floor=0.5,
    volume_cap=1.5,
    sector_sessions=20,
    sector_floor_pct=-5,
    sector_cap_pct=5,
    rr_floor=1,
    rr_cap=3,
    stop_atr_multiple=2,
    target_r_multiple=2,
    pivot_window=5,
    pivot_lookback=250,
)


def ramp(start: float, step: float, n: int = 300) -> pd.Series:
    return pd.Series(start + step * np.arange(n), dtype=float)


def ohlc(close: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99, "close": close})


def test_scale_is_linear_and_clipped() -> None:
    values = pd.Series([-20.0, -10.0, 0.0, 5.0, 10.0, 30.0, math.nan])
    result = scoring.scale(values, -10, 10)
    assert result.iloc[:6].tolist() == [0, 0, 50, 75, 100, 100] and math.isnan(result.iloc[6])


def test_trend_component_extremes_and_warmup() -> None:
    rising, falling = (
        scoring.trend_component(ramp(100, 1), 20),
        scoring.trend_component(ramp(500, -1), 20),
    )
    assert rising.iloc[:199].isna().all()  # needs SMA 200
    assert rising.iloc[-1] == 100 and falling.iloc[-1] == 0


def test_momentum_component_parts() -> None:
    idx = range(4)
    close = pd.Series([100.0, 100, 100, 100], index=idx)
    rsi = pd.Series([60.0, 45.0, 90.0, math.nan], index=idx)
    hist = pd.Series([1.0, -1.0, 1.0, 1.0], index=idx)
    # return over 1 session is 0 everywhere after the first -> not positive -> 0 points
    result = scoring.momentum_component(close, rsi, hist, 1, (50, 70), (40, 80))
    assert math.isnan(result.iloc[0])  # no 1-session return yet
    assert result.iloc[1] == pytest.approx((50 + 0 + 0) / 3)
    assert result.iloc[2] == pytest.approx((0 + 100 + 0) / 3)
    assert math.isnan(result.iloc[3])


def test_total_is_weighted_and_rescales_when_a_component_is_missing() -> None:
    close = ramp(100, 0.5)
    frame = scoring.score_frame(
        ohlc(close), pd.Series(1000.0, index=close.index), close * 0 + 50, None, PARAMS
    )
    last = frame.iloc[-1]
    assert math.isnan(last["sector"]) and last["weight_used"] == 90  # sector weight dropped
    parts = {k: last[k] for k in scoring.COMPONENTS if k != "sector"}
    expected = sum(PARAMS.weights[k] * v for k, v in parts.items()) / 90
    assert last["score"] == pytest.approx(expected)
    assert 0 <= last["score"] <= 100
    assert frame["score"].iloc[:199].isna().all()  # no total before the trend inputs exist

    no_benchmark = scoring.score_frame(
        ohlc(close), pd.Series(1000.0, index=close.index), None, None, PARAMS
    )
    assert no_benchmark["weight_used"].iloc[-1] == 70


def test_reward_risk_uses_target_when_nothing_is_overhead() -> None:
    close = ramp(100, 1)  # new highs every day: no resistance above
    frame = scoring.score_frame(
        ohlc(close), pd.Series(1000.0, index=close.index), None, None, PARAMS
    )
    assert math.isnan(frame["input_nearest_resistance"].iloc[-1])
    assert frame["input_reward_risk"].iloc[-1] == pytest.approx(2.0)  # the planned 2R target
    assert frame["reward_risk"].iloc[-1] == pytest.approx(50.0)


def test_score_has_no_look_ahead(daily: pd.DataFrame, benchmark: pd.DataFrame) -> None:
    adjusted = daily[["open", "high", "low", "close"]]
    volume, bench = daily["volume"], benchmark["close"]
    full = scoring.score_frame(adjusted, volume, bench, bench * 1.1, PARAMS)
    cut = 400
    part = scoring.score_frame(
        adjusted.iloc[:cut], volume.iloc[:cut], bench.iloc[:cut], bench.iloc[:cut] * 1.1, PARAMS
    )
    for column in ["score", *scoring.COMPONENTS, "input_nearest_resistance"]:
        np.testing.assert_allclose(
            full[column].to_numpy()[:cut], part[column].to_numpy(), rtol=1e-9, err_msg=column
        )
    assert full["score"].dropna().between(0, 100).all() and full["weight_used"].iloc[-1] == 100


def test_rejections() -> None:
    close = ramp(100, 0.1, 260)
    adjusted = ohlc(close)
    atr_pct = pd.Series(2.0, index=close.index)
    liquid = scoring.rejection_frame(
        adjusted, close, pd.Series(1e6, index=close.index), atr_pct, 220, 5e7, 6.0
    )
    assert liquid["insufficient_history"].iloc[218] and not liquid["insufficient_history"].iloc[219]
    assert not liquid["rejected"].iloc[-1]
    thin = scoring.rejection_frame(
        adjusted, close, pd.Series(1e3, index=close.index), atr_pct, 220, 5e7, 6.0
    )
    assert thin["insufficient_liquidity"].iloc[-1] and thin["rejected"].iloc[-1]
    wild = scoring.rejection_frame(
        adjusted, close, pd.Series(1e6, index=close.index), atr_pct * 4, 220, 5e7, 6.0
    )
    assert wild["too_volatile"].iloc[-1]
    assert thin["rejected"].iloc[5]  # no 20-session average yet -> cannot be shown liquid


def test_regime_labels_and_no_look_ahead() -> None:
    args = dict(volatility_window=20, trading_days=252, high_vol_percentile=90.0, vol_lookback=500)
    up = regime.regime_frame(ramp(100, 1), **args)  # type: ignore[arg-type]
    falling = pd.Series(500 * 0.997 ** np.arange(300))  # steady percentage decline
    down = regime.regime_frame(falling, **args)  # type: ignore[arg-type]
    assert (up["regime"].iloc[:199] == regime.UNCERTAIN).all()
    assert up["regime"].iloc[-1] == regime.BULLISH and down["regime"].iloc[-1] == regime.BEARISH
    part = regime.regime_frame(ramp(100, 1).iloc[:250], **args)  # type: ignore[arg-type]
    assert part["regime"].tolist() == up["regime"].iloc[:250].tolist()

    # A sudden burst of large swings pushes volatility to the top of its range.
    calm = ramp(100, 1, 400)
    shaken = calm.copy()
    shaken.iloc[380:] = shaken.iloc[380:] * np.where(np.arange(20) % 2 == 0, 1.08, 0.93)
    assert regime.regime_frame(shaken, **args)["regime"].iloc[-1] == regime.UNCERTAIN  # type: ignore[arg-type]


def test_volatility_buckets() -> None:
    ranks = pd.Series([5.0, 50.0, 95.0, math.nan])
    assert regime.volatility_bucket(ranks).tolist() == [
        "Low volatility",
        "Normal volatility",
        "High volatility",
        "Unknown",
    ]


def test_entry_suggestions() -> None:
    def go(**over):  # type: ignore[no-untyped-def]
        args = (
            dict(
                score=75.0,
                rejections=[],
                regime="Bullish",
                freshness="fresh",
                buy_threshold=70,
                watch_threshold=55,
            )
            | over
        )
        return advice.suggest_entry(**args).action

    assert go() == advice.BUY_CANDIDATE
    assert go(regime="Bearish") == advice.WATCH  # risk-off holds back new entries
    assert go(score=60.0) == advice.WATCH and go(score=40.0) == advice.NO_TRADE
    assert go(rejections=["too volatile"]) == advice.REJECTED
    assert go(score=None) == advice.UNAVAILABLE and go(freshness="stale") == advice.UNAVAILABLE


def test_holder_advice() -> None:
    def go(**over):  # type: ignore[no-untyped-def]
        args = (
            dict(
                close=100.0,
                sma_50=95.0,
                trailing_stop=92.0,
                score=60.0,
                regime="Bullish",
                freshness="fresh",
                exit_below=45,
            )
            | over
        )
        return advice.advise_holder(**args)

    assert go().action == advice.HOLD
    assert go(close=91.0).action == advice.EXIT and len(go(close=91.0).reasons) == 2
    assert go(score=30.0).action == advice.EXIT
    assert go(regime="Bearish").action == advice.HEDGE_OR_REDUCE
    assert go(freshness="stale").action == advice.UNAVAILABLE
    assert go(sma_50=None, trailing_stop=None, score=None).action == advice.HOLD


def test_sma_trend_signals_by_hand() -> None:
    close = pd.Series([10.0, 10, 10, 9, 12, 13, 8])
    entries, exits = strategies.sma_trend(close, 3)
    # SMA3: -, -, 10, 9.67, 10.33, 11.33, 11 ; close crosses above on index 4 only
    assert entries.tolist() == [False, False, False, False, True, False, False]
    assert exits.tolist() == [False, False, False, True, False, False, True]


def test_breakout_compares_with_previous_sessions_only() -> None:
    high = pd.Series([10.0, 11, 12, 12, 13])
    low, close = high - 2, pd.Series([9.0, 10, 11, 12.5, 12])
    entries, _ = strategies.breakout(high, low, close, enter=3, leave=2)
    # day 3: prior 3 highs max = 12, close 12.5 > 12 -> entry. Day 4's own high (13) is not used.
    assert entries.tolist() == [False, False, False, True, False]


def test_score_model_signals() -> None:
    score = pd.Series([80.0, 80, 50, 40, math.nan])
    rejected = pd.Series([False, True, False, False, False])
    entries, exits = strategies.score_model(score, rejected, 70, 45)
    assert entries.tolist() == [True, False, False, False, False]
    assert exits.tolist() == [False, False, False, True, False]
    assert len(strategies.catalogue(70, 45)) == 6
    assert len({s.key for s in strategies.catalogue(70, 45)}) == 6
    assert sum(s.baseline for s in strategies.catalogue(70, 45)) == 1


def test_beta() -> None:
    rng = np.random.default_rng(3)
    bench = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, 200)))
    doubled = pd.Series(100 * np.cumprod(1 + 2 * bench.pct_change().fillna(0)))
    value = ind.beta(doubled, bench, 120)
    assert value is not None and value[0] == pytest.approx(2.0) and value[1] == pytest.approx(1.0)
    assert ind.beta(doubled.iloc[:50], bench.iloc[:50], 120) is None
