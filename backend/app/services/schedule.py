"""When the publishing workflow should run next.

GitHub's own cron is best-effort: scheduled runs can be late by hours or skipped. So each run
of `.github/workflows/publish-site.yml` works out when the next one is due, waits, and starts
it. This module is that decision; `python -m app.next_run` prints it for the workflow.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass

from app.services.calendars import MarketCalendar, as_utc


@dataclass(frozen=True)
class NextRun:
    at: dt.datetime
    reason: str


def active_market(
    calendar: MarketCalendar, now: dt.datetime, close_buffer: dt.timedelta, every: dt.timedelta
) -> bool:
    """True from a session's open until one interval after its close plus the buffer.

    The extra interval makes sure one run lands after the buffer, when the day's candle
    counts as completed.
    """
    now = as_utc(now)
    local_today = now.astimezone(calendar.tz).date()
    for session in calendar.sessions_between(local_today - dt.timedelta(days=1), local_today):
        start = calendar.session_open_utc(session)
        end = calendar.session_close_utc(session) + close_buffer + every
        if start <= now < end:
            return True
    return False


def next_run(
    calendars: Iterable[MarketCalendar],
    now: dt.datetime,
    started: dt.datetime,
    every: dt.timedelta,
    idle_max: dt.timedelta,
    close_buffer: dt.timedelta,
) -> NextRun:
    """Next run time.

    While any market is active: `every` after this run started. Otherwise: the next session
    open (whichever market is first), but no later than `idle_max` from now, so late
    candles and corporate actions are still picked up when markets are closed.
    """
    now, started = as_utc(now), as_utc(started)
    calendars = list(calendars)
    active = [c.market for c in calendars if active_market(c, now, close_buffer, every)]
    if active:
        return NextRun(max(started + every, now), f"session active: {', '.join(active)}")

    opens: list[tuple[dt.datetime, str]] = []
    for calendar in calendars:
        session = calendar.next_session(now)
        if session is not None:
            opens.append((calendar.session_open_utc(session), calendar.market))
    latest = now + idle_max
    if opens:
        first, market = min(opens)
        if first <= latest:
            return NextRun(max(first, now), f"next session opens: {market}")
    return NextRun(latest, "markets closed: idle check")
