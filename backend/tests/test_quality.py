from __future__ import annotations

import datetime as dt
import math

from app.core import quality
from app.providers.base import RawBar

D = dt.date


def bar(day: dt.date, close: float = 100.0, volume: float = 1000.0, **over: float) -> RawBar:
    values = {
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "adj_close": close,
    }
    values.update(over)
    return RawBar(date=day, volume=volume, **values)


def test_rejects_unusable_rows() -> None:
    bars = [
        bar(D(2024, 1, 2)),
        bar(D(2024, 1, 3), high=90.0, low=95.0),  # high below low
        bar(D(2024, 1, 4), close=-5.0),  # negative price
        bar(D(2024, 1, 5), open=math.nan),  # NaN price
        bar(D(2024, 1, 8), volume=-1.0),  # negative volume
        bar(D(2024, 1, 9), adj_close=0.0),  # zero price
    ]
    valid, issues = quality.validate_bars(bars, is_index=False)
    assert [b.date for b in valid] == [D(2024, 1, 2)]
    rejected = {i.date: i.detail for i in issues if i.kind == quality.REJECTED_ROW}
    assert set(rejected) == {
        D(2024, 1, 3),
        D(2024, 1, 4),
        D(2024, 1, 5),
        D(2024, 1, 8),
        D(2024, 1, 9),
    }
    assert "below low" in rejected[D(2024, 1, 3)]


def test_duplicate_dates_keep_one_row() -> None:
    bars = [bar(D(2024, 1, 2), close=100.0), bar(D(2024, 1, 2), close=101.0), bar(D(2024, 1, 3))]
    valid, issues = quality.validate_bars(bars, is_index=False)
    assert [b.date for b in valid] == [D(2024, 1, 2), D(2024, 1, 3)]
    assert valid[0].close == 101.0  # the later row wins
    assert [i.kind for i in issues] == [quality.DUPLICATE_ROW]


def test_zero_volume_flagged_for_stocks_but_not_indices() -> None:
    bars = [bar(D(2024, 1, 2), volume=0.0)]
    stock_valid, stock_issues = quality.validate_bars(bars, is_index=False)
    index_valid, index_issues = quality.validate_bars(bars, is_index=True)
    assert len(stock_valid) == len(index_valid) == 1  # kept either way
    assert [i.kind for i in stock_issues] == [quality.ZERO_VOLUME]
    assert index_issues == []


def test_partial_candle_is_excluded() -> None:
    bars = [bar(D(2024, 3, 7)), bar(D(2024, 3, 8)), bar(D(2024, 3, 11))]
    kept, dropped = quality.drop_incomplete(bars, last_completed_session=D(2024, 3, 8))
    assert [b.date for b in kept] == [D(2024, 3, 7), D(2024, 3, 8)]
    assert [b.date for b in dropped] == [D(2024, 3, 11)]


def test_data_gaps_are_reported_against_expected_sessions() -> None:
    expected = [D(2024, 3, 4), D(2024, 3, 5), D(2024, 3, 6), D(2024, 3, 7), D(2024, 3, 8)]
    stored = [D(2024, 3, 5), D(2024, 3, 7), D(2024, 3, 8)]
    # 3/4 is before the first stored candle, so it is not a gap; 3/6 is.
    assert quality.find_missing_sessions(stored, expected) == [D(2024, 3, 6)]
    assert quality.find_missing_sessions([], expected) == []


def test_weekend_dates_are_never_gaps() -> None:
    expected = [D(2024, 3, 8), D(2024, 3, 11)]  # Friday, Monday
    assert quality.find_missing_sessions(expected, expected) == []


def test_unexpected_sessions_are_reported() -> None:
    expected = [D(2024, 3, 7), D(2024, 3, 8), D(2024, 3, 11)]
    stored = [D(2024, 3, 7), D(2024, 3, 8), D(2024, 3, 9), D(2024, 3, 11)]
    assert quality.find_unexpected_sessions(stored, expected) == [D(2024, 3, 9)]


def test_suspicious_move_without_a_recorded_split() -> None:
    bars = [
        bar(D(2024, 1, 2), close=200.0),
        bar(D(2024, 1, 3), close=100.0),
        bar(D(2024, 1, 4), close=101.0),
    ]
    flagged = quality.find_suspicious_moves(bars, split_dates=[], threshold_pct=25.0)
    assert [(i.kind, i.date) for i in flagged] == [(quality.SUSPICIOUS_MOVE, D(2024, 1, 3))]
    assert "-50.0%" in flagged[0].detail


def test_move_on_a_recorded_split_date_is_not_flagged() -> None:
    bars = [bar(D(2024, 1, 2), close=200.0), bar(D(2024, 1, 3), close=100.0)]
    assert quality.find_suspicious_moves(bars, [D(2024, 1, 3)], threshold_pct=25.0) == []


def test_unadjusted_split_fixture_is_flagged(split) -> None:  # type: ignore[no-untyped-def]
    """Raw prices from the split fixture look like a -50% crash unless the split is known."""
    raw = [bar(r.date, close=r.raw_close) for r in split.itertuples()]
    split_day = split.loc[split["split_ratio"] > 0, "date"].iloc[0]
    assert [i.date for i in quality.find_suspicious_moves(raw, [], 25.0)] == [split_day]
    assert quality.find_suspicious_moves(raw, [split_day], 25.0) == []
    adjusted = [bar(r.date, close=r.close) for r in split.itertuples()]
    assert quality.find_suspicious_moves(adjusted, [], 25.0) == []
