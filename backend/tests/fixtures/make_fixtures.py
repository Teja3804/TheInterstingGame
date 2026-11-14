"""Regenerates the SYNTHETIC fixture CSVs in this folder (fixed seed, no market data).

    python tests/fixtures/make_fixtures.py

Nothing here comes from a real security. Prices are a seeded random walk.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
HEADER = "# SYNTHETIC test data (seeded random walk). Not real market prices.\n"


def _walk(seed: int, rows: int, start: float) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = start * np.exp(np.cumsum(rng.normal(0.0004, 0.015, rows)))
    open_ = close * (1 + rng.normal(0, 0.004, rows))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.005, rows)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.005, rows)))
    volume = rng.integers(500_000, 5_000_000, rows).astype(float)
    dates = pd.bdate_range("2023-01-02", periods=rows)
    return pd.DataFrame(
        {
            "date": dates.date,
            "open": open_.round(4),
            "high": high.round(4),
            "low": low.round(4),
            "close": close.round(4),
            "adj_close": close.round(4),
            "volume": volume,
        }
    )


def _write(name: str, frame: pd.DataFrame, note: str = "") -> None:
    with (HERE / name).open("w", encoding="utf-8") as handle:
        handle.write(HEADER)
        if note:
            handle.write(f"# {note}\n")
        frame.to_csv(handle, index=False)


def main() -> None:
    _write("synthetic_daily.csv", _walk(seed=7, rows=520, start=100.0))
    _write("synthetic_benchmark.csv", _walk(seed=11, rows=520, start=4000.0))

    # A 2-for-1 split on row 150. raw_* is what traded (halves at the split);
    # open/high/low/close are split-adjusted, the way the provider reports them.
    base = _walk(seed=23, rows=300, start=200.0)
    factor = np.where(np.arange(len(base)) < 150, 2.0, 1.0)
    split = base.copy()
    for column in ("open", "high", "low", "close"):
        split[f"raw_{column}"] = (base[column] * factor).round(4)
    split["split_ratio"] = 0.0
    split.loc[150, "split_ratio"] = 2.0
    _write("synthetic_split.csv", split, "2-for-1 split on the row where split_ratio = 2.")


if __name__ == "__main__":
    main()
