"""Freshness classification (CONTEXT.md section 4). Pure: the caller supplies both dates."""

from __future__ import annotations

import datetime as dt

FRESH = "fresh"
STALE = "stale"
MISSING = "missing"
UNKNOWN = "unknown"


def classify(latest_candle: dt.date | None, last_completed_session: dt.date | None) -> str:
    """fresh   = latest stored candle is the last completed session
    stale   = latest stored candle is older than the last completed session
    missing = nothing stored
    unknown = the calendar could not name a last completed session

    The last completed session already skips weekends and holidays, so those never
    produce a stale result.
    """
    if latest_candle is None:
        return MISSING
    if last_completed_session is None:
        return UNKNOWN
    return FRESH if latest_candle >= last_completed_session else STALE
