"""Pure data-quality checks on daily candles. No network, no database, no clock."""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.providers.base import RawBar


@dataclass(frozen=True)
class Issue:
    kind: str
    detail: str
    date: dt.date | None = None


# Issue kinds
REJECTED_ROW = "rejected_row"
DUPLICATE_ROW = "duplicate_row"
ZERO_VOLUME = "zero_volume"
SUSPICIOUS_MOVE = "suspicious_move"
MISSING_SESSION = "missing_session"
PARTIAL_CANDLE = "partial_candle_dropped"
UNEXPECTED_SESSION = "unexpected_session"


def drop_incomplete(
    bars: Sequence[RawBar], last_completed_session: dt.date
) -> tuple[list[RawBar], list[RawBar]]:
    """Split bars into (completed, dropped). A bar dated after the last completed session
    is an in-progress candle and must not be stored or analysed."""
    kept = [b for b in bars if b.date <= last_completed_session]
    dropped = [b for b in bars if b.date > last_completed_session]
    return kept, dropped


def _row_problem(bar: RawBar) -> str | None:
    prices = {
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "adj_close": bar.adj_close,
    }
    for name, value in prices.items():
        if not math.isfinite(value):
            return f"{name} is not a number"
        if value <= 0:
            return f"{name} is not positive ({value})"
    if bar.high < bar.low:
        return f"high {bar.high} is below low {bar.low}"
    if not math.isfinite(bar.volume):
        return "volume is not a number"
    if bar.volume < 0:
        return f"volume is negative ({bar.volume})"
    return None


def validate_bars(bars: Sequence[RawBar], is_index: bool) -> tuple[list[RawBar], list[Issue]]:
    """Reject unusable rows and flag questionable ones.

    Rejected: NaN / non-positive prices, high < low, NaN / negative volume.
    Duplicated dates keep the last row. Zero volume is flagged for stocks only,
    because indices legitimately report zero volume.
    """
    issues: list[Issue] = []
    by_date: dict[dt.date, RawBar] = {}
    for bar in bars:
        problem = _row_problem(bar)
        if problem is not None:
            issues.append(Issue(REJECTED_ROW, problem, bar.date))
            continue
        if bar.date in by_date:
            issues.append(Issue(DUPLICATE_ROW, "provider returned this date twice", bar.date))
        by_date[bar.date] = bar
    valid = [by_date[d] for d in sorted(by_date)]
    if not is_index:
        issues.extend(
            Issue(ZERO_VOLUME, "zero volume on a trading session", b.date)
            for b in valid
            if b.volume == 0
        )
    return valid, issues


def find_suspicious_moves(
    bars: Sequence[RawBar], split_dates: Iterable[dt.date], threshold_pct: float
) -> list[Issue]:
    """Flag large single-day moves in `close` with no split recorded on that date.

    `close` is already split-adjusted by the provider, so a jump of this size without a
    recorded split may be an unadjusted corporate action (or a genuine extreme move).
    """
    splits = set(split_dates)
    ordered = sorted(bars, key=lambda b: b.date)
    issues: list[Issue] = []
    for previous, current in zip(ordered, ordered[1:], strict=False):
        change_pct = (current.close / previous.close - 1.0) * 100.0
        if abs(change_pct) >= threshold_pct and current.date not in splits:
            issues.append(
                Issue(
                    SUSPICIOUS_MOVE,
                    f"close moved {change_pct:+.1f}% in one session with no recorded split; "
                    "possible unadjusted corporate action",
                    current.date,
                )
            )
    return issues


def find_missing_sessions(
    stored_dates: Iterable[dt.date], expected_sessions: Iterable[dt.date]
) -> list[dt.date]:
    """Calendar sessions with no stored candle, between the first stored date and the
    end of the expected range. Weekends and holidays are never in `expected_sessions`."""
    stored = set(stored_dates)
    if not stored:
        return []
    first = min(stored)
    return sorted(d for d in expected_sessions if d >= first and d not in stored)


def find_unexpected_sessions(
    stored_dates: Iterable[dt.date], expected_sessions: Iterable[dt.date]
) -> list[dt.date]:
    """Stored candles on dates the calendar says were not sessions (calendar mismatch,
    special sessions). Reported as information, never rejected."""
    expected = set(expected_sessions)
    if not expected:
        return []
    low, high = min(expected), max(expected)
    return sorted(d for d in set(stored_dates) if low <= d <= high and d not in expected)
