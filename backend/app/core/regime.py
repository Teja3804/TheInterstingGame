"""Market regime from a benchmark's adjusted closes (CONTEXT.md section 6). Pure."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.core import indicators as ind

BULLISH, NEUTRAL, BEARISH, UNCERTAIN = "Bullish", "Neutral", "Bearish", "Uncertain"


def regime_frame(
    close: pd.Series,
    volatility_window: int,
    trading_days: int,
    high_vol_percentile: float,
    vol_lookback: int,
) -> pd.DataFrame:
    """Label per day plus the evidence. Uses only data up to each day.

    Bullish:   close > SMA 200 and SMA 50 > SMA 200
    Bearish:   close < SMA 200 and SMA 50 < SMA 200
    Neutral:   anything else
    Uncertain: SMA 200 not available yet, or volatility above the given percentile of its
               own trailing history (overrides the labels above)
    """
    sma50, sma200 = ind.sma(close, 50), ind.sma(close, 200)
    vol = ind.volatility(close, volatility_window, trading_days)
    # Percentile rank of today's volatility within the trailing window (inclusive of today).
    vol_rank = vol.rolling(vol_lookback, min_periods=60).rank(pct=True) * 100.0

    label = pd.Series(NEUTRAL, index=close.index, dtype=object)
    label[(close > sma200) & (sma50 > sma200)] = BULLISH
    label[(close < sma200) & (sma50 < sma200)] = BEARISH
    label[vol_rank > high_vol_percentile] = UNCERTAIN
    label[sma200.isna()] = UNCERTAIN
    return pd.DataFrame(
        {
            "regime": label,
            "close": close,
            "sma_50": sma50,
            "sma_200": sma200,
            "volatility": vol,
            "volatility_percentile": vol_rank,
        }
    )


def volatility_bucket(vol_rank: pd.Series) -> pd.Series:
    """Low / Normal / High by thirds of the trailing percentile rank. NaN -> 'Unknown'."""
    bucket = pd.Series("Unknown", index=vol_rank.index, dtype=object)
    bucket[vol_rank <= 100 / 3] = "Low volatility"
    bucket[(vol_rank > 100 / 3) & (vol_rank <= 200 / 3)] = "Normal volatility"
    bucket[vol_rank > 200 / 3] = "High volatility"
    bucket[np.asarray(vol_rank.isna())] = "Unknown"
    return bucket
