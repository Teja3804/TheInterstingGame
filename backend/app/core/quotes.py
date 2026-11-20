"""Checks on a latest-price quote. Pure functions: no network, no database."""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field

# Warning kinds attached to a quote.
NOT_POSITIVE = "price_not_positive"
FUTURE_TIME = "time_in_future"
CURRENCY_MISMATCH = "currency_mismatch"
LARGE_MOVE = "large_move"
CLOSE_MISMATCH = "close_mismatch"

# What the price represents.
DURING_SESSION = "during_session"  # the market is open: a delayed price from today's session
AFTER_CLOSE = "after_close"  # the market is closed: the price is the last session's close


@dataclass(frozen=True)
class QuoteCheck:
    usable: bool
    warnings: list[str] = field(default_factory=list)


def previous_close(closes: list[tuple[dt.date, float]], session: dt.date) -> float | None:
    """Close of the last daily row dated before `session`, or None if there is none."""
    earlier = [(day, value) for day, value in closes if day < session and math.isfinite(value)]
    if not earlier:
        return None
    return max(earlier)[1]


def change_pct(price: float, reference: float | None) -> float | None:
    if reference is None or reference <= 0 or not math.isfinite(reference):
        return None
    return (price / reference - 1.0) * 100.0


def check_quote(
    *,
    price: float,
    market_time_utc: dt.datetime,
    currency: str | None,
    expected_currency: str,
    reference_close: float | None,
    stored_close_same_session: float | None,
    now_utc: dt.datetime,
    max_future_seconds: float,
    suspicious_move_pct: float,
    close_match_tolerance_pct: float,
) -> QuoteCheck:
    """Validate a quote before it is stored.

    A quote is unusable when the price is not a positive number or its time is in the
    future. Other findings are warnings: the price is kept and the warning is shown.
    `stored_close_same_session` is the stored completed candle's close for the same session
    as the quote, if there is one; a mismatch means the two Yahoo endpoints disagree.
    """
    if not math.isfinite(price) or price <= 0:
        return QuoteCheck(False, [f"{NOT_POSITIVE}: provider returned {price}"])
    ahead = (market_time_utc - now_utc).total_seconds()
    if ahead > max_future_seconds:
        return QuoteCheck(False, [f"{FUTURE_TIME}: quote time is {ahead:.0f}s ahead of now"])

    warnings: list[str] = []
    if currency is not None and currency != expected_currency:
        warnings.append(
            f"{CURRENCY_MISMATCH}: provider says {currency}, expected {expected_currency}"
        )
    move = change_pct(price, reference_close)
    if move is not None and abs(move) > suspicious_move_pct:
        warnings.append(f"{LARGE_MOVE}: {move:+.1f}% versus the previous close")
    gap = change_pct(price, stored_close_same_session)
    if gap is not None and abs(gap) > close_match_tolerance_pct:
        warnings.append(
            f"{CLOSE_MISMATCH}: quote differs from the stored close for the same session "
            f"by {gap:+.2f}%"
        )
    return QuoteCheck(True, warnings)
