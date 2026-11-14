"""Indicator maths, checked two ways: hand-calculated values on a tiny series, and simple
independent loop implementations on a long synthetic series."""

from __future__ import annotations

import math
import statistics

import numpy as np
import pandas as pd
import pytest

from app.core import indicators as ind

# ---------------------------------------------------------------------------------------
# Independent reference implementations (plain Python loops, written separately).
# ---------------------------------------------------------------------------------------


def ref_sma(xs: list[float], n: int) -> list[float]:
    return [math.nan if i + 1 < n else sum(xs[i + 1 - n : i + 1]) / n for i in range(len(xs))]


def ref_smoothed(xs: list[float], n: int, alpha: float) -> list[float]:
    """Seeded with the mean of the first n finite values (leading NaNs skipped)."""
    out = [math.nan] * len(xs)
    first = next((i for i, x in enumerate(xs) if not math.isnan(x)), None)
    if first is None or first + n > len(xs):
        return out
    out[first + n - 1] = sum(xs[first : first + n]) / n
    for i in range(first + n, len(xs)):
        out[i] = alpha * xs[i] + (1 - alpha) * out[i - 1]
    return out


def ref_ema(xs: list[float], n: int) -> list[float]:
    return ref_smoothed(xs, n, 2 / (n + 1))


def ref_rsi(xs: list[float], n: int) -> list[float]:
    gains = [math.nan] + [max(xs[i] - xs[i - 1], 0.0) for i in range(1, len(xs))]
    losses = [math.nan] + [max(xs[i - 1] - xs[i], 0.0) for i in range(1, len(xs))]
    avg_gain, avg_loss = ref_smoothed(gains, n, 1 / n), ref_smoothed(losses, n, 1 / n)
    out = []
    for g, loss in zip(avg_gain, avg_loss, strict=True):
        if math.isnan(g):
            out.append(math.nan)
        elif loss == 0:
            out.append(100.0 if g > 0 else math.nan)
        else:
            out.append(100 - 100 / (1 + g / loss))
    return out


def ref_true_range(h: list[float], lo: list[float], c: list[float]) -> list[float]:
    return [math.nan] + [
        max(h[i] - lo[i], abs(h[i] - c[i - 1]), abs(lo[i] - c[i - 1])) for i in range(1, len(c))
    ]


def assert_series_close(actual: pd.Series, expected: list[float]) -> None:
    np.testing.assert_allclose(
        actual.to_numpy(dtype=float), np.array(expected), rtol=1e-9, atol=1e-9
    )


# ---------------------------------------------------------------------------------------
# Hand-calculated values. closes = 10, 11, 12, 11, 13, 14, 12
# ---------------------------------------------------------------------------------------


def test_sma_hand(hand: pd.DataFrame) -> None:
    result = ind.sma(hand["close"], 3)
    assert result.iloc[:2].isna().all()
    assert result.iloc[2:].tolist() == pytest.approx([11, 34 / 3, 12, 38 / 3, 13])


def test_ema_hand(hand: pd.DataFrame) -> None:
    # alpha = 0.5, seed = SMA(10, 11, 12) = 11, then 11, 12, 13, 12.5
    result = ind.ema(hand["close"], 3)
    assert result.iloc[:2].isna().all()
    assert result.iloc[2:].tolist() == pytest.approx([11, 11, 12, 13, 12.5])


def test_rsi_hand(hand: pd.DataFrame) -> None:
    # changes +1 +1 -1 +2 +1 -2, period 3.
    # seed: gain 2/3, loss 1/3 -> RS 2    -> 66.6667
    # next: gain 10/9, loss 2/9 -> RS 5   -> 83.3333
    # next: gain 29/27, loss 4/27 -> RS 7.25 -> 87.8788
    # next: gain 58/81, loss 62/81 -> RS 58/62 -> 48.3333
    result = ind.rsi(hand["close"], 3)
    assert result.iloc[:3].isna().all()
    assert result.iloc[3:].tolist() == pytest.approx(
        [200 / 3, 250 / 3, 100 - 100 / 8.25, 100 - 100 / (1 + 58 / 62)]
    )


def test_true_range_and_atr_hand(hand: pd.DataFrame) -> None:
    tr = ind.true_range(hand["high"], hand["low"], hand["close"])
    assert math.isnan(tr.iloc[0])
    assert tr.iloc[1:].tolist() == [2, 2, 2, 3, 3, 3]
    # seed mean(2, 2, 2) = 2, then 2 + 1/3, then + (3 - 2.3333)/3, ...
    atr = ind.atr(hand["high"], hand["low"], hand["close"], 3)
    assert atr.iloc[:3].isna().all()
    assert atr.iloc[3:].tolist() == pytest.approx([2, 7 / 3, 23 / 9, 73 / 27])


def test_bollinger_hand(hand: pd.DataFrame) -> None:
    # last three closes 13, 14, 12: mean 13, population std sqrt(2/3)
    bands = ind.bollinger(hand["close"], 3, 2.0)
    sigma = math.sqrt(2 / 3)
    assert bands["middle"].iloc[-1] == pytest.approx(13)
    assert bands["upper"].iloc[-1] == pytest.approx(13 + 2 * sigma)
    assert bands["lower"].iloc[-1] == pytest.approx(13 - 2 * sigma)


def test_relative_volume_uses_previous_sessions_only(hand: pd.DataFrame) -> None:
    result = ind.relative_volume(hand["volume"], 3)
    assert result.iloc[:3].isna().all()
    assert result.iloc[3] == pytest.approx(400 / 200)  # mean(100, 200, 300)
    assert result.iloc[6] == pytest.approx(900 / 500)  # mean(400, 500, 600), not today's 900


def test_returns_and_drawdown_hand(hand: pd.DataFrame) -> None:
    assert ind.session_return(hand["close"], 2).iloc[-1] == pytest.approx(12 / 13 - 1)
    assert ind.session_return(hand["close"], 1).iloc[1] == pytest.approx(0.1)
    dd = ind.drawdown(hand["close"])
    assert dd.tolist() == pytest.approx([0, 0, 0, 11 / 12 - 1, 0, 0, 12 / 14 - 1])
    assert ind.max_drawdown(hand["close"]) == pytest.approx(12 / 14 - 1)


def test_pivots_hand(hand: pd.DataFrame) -> None:
    # highs 11 12 13 12 14 15 14 ; lows 9 10 11 10 11 12 11 ; one candle each side
    pivots = ind.confirmed_pivots(hand["high"], hand["low"], 1)
    assert [(p.position, p.kind, p.price, p.confirmed_position) for p in pivots] == [
        (2, "high", 13.0, 3),
        (3, "low", 10.0, 4),
        (5, "high", 15.0, 6),
    ]
    support, resistance = ind.support_resistance(
        hand["high"], hand["low"], hand["close"], window=1, lookback=50, max_levels=3
    )
    assert [p.price for p in support] == [10.0]  # below the last close of 12
    assert [p.price for p in resistance] == [13.0, 15.0]  # nearest first


def test_pivot_needs_later_candles_to_confirm(hand: pd.DataFrame) -> None:
    # Cut the series right after the 15 high: it cannot be called a pivot yet.
    cut = hand.iloc[:6]
    pivots = ind.confirmed_pivots(cut["high"], cut["low"], 1)
    assert all(p.position != 5 for p in pivots)


# ---------------------------------------------------------------------------------------
# Reference comparisons on the 520-row synthetic series, with production parameters.
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("window", [20, 50, 200])
def test_sma_matches_reference(daily: pd.DataFrame, window: int) -> None:
    assert_series_close(ind.sma(daily["close"], window), ref_sma(daily["close"].tolist(), window))


@pytest.mark.parametrize("window", [9, 21])
def test_ema_matches_reference(daily: pd.DataFrame, window: int) -> None:
    assert_series_close(ind.ema(daily["close"], window), ref_ema(daily["close"].tolist(), window))


def test_rsi_matches_reference(daily: pd.DataFrame) -> None:
    result = ind.rsi(daily["close"], 14)
    assert_series_close(result, ref_rsi(daily["close"].tolist(), 14))
    assert result.iloc[:14].isna().all() and not math.isnan(result.iloc[14])
    assert result.dropna().between(0, 100).all()


def test_macd_matches_reference(daily: pd.DataFrame) -> None:
    closes = daily["close"].tolist()
    fast, slow = ref_ema(closes, 12), ref_ema(closes, 26)
    line = [f - s for f, s in zip(fast, slow, strict=True)]
    signal = ref_ema(line, 9)
    result = ind.macd(daily["close"], 12, 26, 9)
    assert_series_close(result["macd"], line)
    assert_series_close(result["signal"], signal)
    assert_series_close(result["histogram"], [m - s for m, s in zip(line, signal, strict=True)])
    assert result["macd"].iloc[:25].isna().all() and not math.isnan(result["macd"].iloc[25])
    assert result["signal"].iloc[:33].isna().all() and not math.isnan(result["signal"].iloc[33])


def test_atr_matches_reference(daily: pd.DataFrame) -> None:
    tr = ref_true_range(daily["high"].tolist(), daily["low"].tolist(), daily["close"].tolist())
    result = ind.atr(daily["high"], daily["low"], daily["close"], 14)
    assert_series_close(result, ref_smoothed(tr, 14, 1 / 14))
    assert result.iloc[:14].isna().all() and not math.isnan(result.iloc[14])


def test_bollinger_matches_reference(daily: pd.DataFrame) -> None:
    closes = daily["close"].tolist()
    bands = ind.bollinger(daily["close"], 20, 2.0)
    for i in (19, 100, 519):
        window = closes[i - 19 : i + 1]
        mean, sigma = statistics.fmean(window), statistics.pstdev(window)
        assert bands["middle"].iloc[i] == pytest.approx(mean)
        assert bands["upper"].iloc[i] == pytest.approx(mean + 2 * sigma)
        assert bands["lower"].iloc[i] == pytest.approx(mean - 2 * sigma)
    assert bands.iloc[:19].isna().all().all()


def test_volatility_matches_reference(daily: pd.DataFrame) -> None:
    closes = daily["close"].tolist()
    result = ind.volatility(daily["close"], 20, 252)
    for i in (20, 250, 519):
        returns = [closes[j] / closes[j - 1] - 1 for j in range(i - 19, i + 1)]
        assert result.iloc[i] == pytest.approx(statistics.stdev(returns) * math.sqrt(252))
    assert result.iloc[:20].isna().all()


def test_relative_strength_is_excess_return(daily: pd.DataFrame, benchmark: pd.DataFrame) -> None:
    stock = daily.set_index("date")["close"]
    bench = benchmark.set_index("date")["close"]
    result = ind.relative_strength(stock, bench, 20)
    expected = (stock.iloc[-1] / stock.iloc[-21] - 1) - (bench.iloc[-1] / bench.iloc[-21] - 1)
    assert result.iloc[-1] == pytest.approx(expected)
    assert result.iloc[:20].isna().all()


def test_relative_strength_is_nan_when_benchmark_lacks_the_date(
    daily: pd.DataFrame, benchmark: pd.DataFrame
) -> None:
    stock = daily.set_index("date")["close"]
    bench = benchmark.set_index("date")["close"].iloc[:-1]  # benchmark one session behind
    result = ind.relative_strength(stock, bench, 20)
    assert math.isnan(result.iloc[-1])
    assert not math.isnan(result.iloc[-2])


# ---------------------------------------------------------------------------------------
# Insufficient data and look-ahead
# ---------------------------------------------------------------------------------------


def test_insufficient_history_gives_nan_not_a_guess(hand: pd.DataFrame) -> None:
    close, high, low, volume = hand["close"], hand["high"], hand["low"], hand["volume"]
    assert ind.sma(close, 20).isna().all()
    assert ind.ema(close, 9).isna().all()
    assert ind.rsi(close, 14).isna().all()
    assert ind.macd(close, 12, 26, 9).isna().all().all()
    assert ind.atr(high, low, close, 14).isna().all()
    assert ind.bollinger(close, 20, 2.0).isna().all().all()
    assert ind.relative_volume(volume, 20).isna().all()
    assert ind.session_return(close, 20).isna().all()
    assert ind.volatility(close, 20, 252).isna().all()


def test_flat_prices_have_undefined_rsi() -> None:
    assert ind.rsi(pd.Series([5.0] * 30), 14).isna().all()


def test_no_look_ahead(daily: pd.DataFrame, benchmark: pd.DataFrame) -> None:
    """A value for date D must not change when later candles are added."""
    cut = 300
    full, part = daily, daily.iloc[:cut]
    bench_full = benchmark.set_index("date")["close"]

    def compute(frame: pd.DataFrame) -> dict[str, pd.Series]:
        c, h, lo, v = frame["close"], frame["high"], frame["low"], frame["volume"]
        macd = ind.macd(c, 12, 26, 9)
        bands = ind.bollinger(c, 20, 2.0)
        indexed = frame.set_index("date")["close"]
        return {
            "sma": ind.sma(c, 50),
            "ema": ind.ema(c, 21),
            "rsi": ind.rsi(c, 14),
            "macd": macd["macd"],
            "signal": macd["signal"],
            "atr": ind.atr(h, lo, c, 14),
            "upper": bands["upper"],
            "relvol": ind.relative_volume(v, 20),
            "ret": ind.session_return(c, 20),
            "vol": ind.volatility(c, 20, 252),
            "dd": ind.drawdown(c),
            "rs": ind.relative_strength(indexed, bench_full.loc[: indexed.index[-1]], 20),
        }

    for name, (whole, partial) in {
        k: (compute(full)[k], compute(part)[k]) for k in compute(part)
    }.items():
        np.testing.assert_allclose(
            whole.to_numpy(dtype=float)[:cut],
            partial.to_numpy(dtype=float),
            rtol=1e-12,
            err_msg=name,
        )

    pivots_full = ind.confirmed_pivots(full["high"], full["low"], 5)
    pivots_part = ind.confirmed_pivots(part["high"], part["low"], 5)
    assert pivots_part == [p for p in pivots_full if p.confirmed_position < cut]


# ---------------------------------------------------------------------------------------
# Stock split
# ---------------------------------------------------------------------------------------


def test_split_adjusted_prices_show_no_break_at_the_split(split: pd.DataFrame) -> None:
    at = int(split.index[split["split_ratio"] > 0][0])
    raw_move = split["raw_close"].iloc[at] / split["raw_close"].iloc[at - 1] - 1
    adjusted_move = split["adj_close"].iloc[at] / split["adj_close"].iloc[at - 1] - 1
    assert raw_move < -0.4  # the unadjusted price halves on a 2-for-1 split
    assert abs(adjusted_move) < 0.1  # the adjusted series carries on as normal

    # Indicators on raw prices would report a crash that never happened.
    raw_rsi = ind.rsi(split["raw_close"], 14).iloc[at]
    adjusted_rsi = ind.rsi(split["adj_close"], 14).iloc[at]
    assert raw_rsi < 20 < adjusted_rsi
    assert ind.session_return(split["raw_close"], 1).iloc[at] == pytest.approx(raw_move)


def test_indicators_on_adjusted_series_equal_a_series_that_never_split(split: pd.DataFrame) -> None:
    """Adjusting raw prices by the split ratio must reproduce the adjusted series, and so
    every indicator computed from it."""
    at = int(split.index[split["split_ratio"] > 0][0])
    ratio = float(split["split_ratio"].iloc[at])
    factor = pd.Series(np.where(split.index < at, 1 / ratio, 1.0), index=split.index)
    rebuilt_close = split["raw_close"] * factor
    np.testing.assert_allclose(rebuilt_close, split["close"], rtol=1e-4)
    np.testing.assert_allclose(
        ind.sma(rebuilt_close, 50).dropna(), ind.sma(split["close"], 50).dropna(), rtol=1e-4
    )
    np.testing.assert_allclose(
        ind.rsi(rebuilt_close, 14).dropna(), ind.rsi(split["close"], 14).dropna(), rtol=1e-2
    )


def test_adjust_ohlc_scales_whole_candle_by_adj_close_over_close(hand: pd.DataFrame) -> None:
    adj_close = hand["close"] * 0.5  # e.g. the effect of later distributions
    adjusted = ind.adjust_ohlc(hand["open"], hand["high"], hand["low"], hand["close"], adj_close)
    assert adjusted["close"].tolist() == adj_close.tolist()
    assert adjusted["high"].tolist() == pytest.approx((hand["high"] * 0.5).tolist())
    assert adjusted["low"].tolist() == pytest.approx((hand["low"] * 0.5).tolist())
    assert adjusted["open"].tolist() == pytest.approx((hand["open"] * 0.5).tolist())
    # Ratios inside a candle are preserved, so ATR% and RSI are unaffected by the scale.
    assert (adjusted["high"] / adjusted["low"]).tolist() == pytest.approx(
        (hand["high"] / hand["low"]).tolist()
    )
