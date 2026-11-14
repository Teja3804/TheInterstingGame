"""Market sessions and time zones, from the exchange_calendars library (never hardcoded)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

from app.config import MarketConfig, SessionsConfig

UTC = dt.UTC


def utc_now() -> dt.datetime:
    return dt.datetime.now(UTC)


def to_naive_utc(moment: dt.datetime) -> dt.datetime:
    """Storage format: naive datetime in UTC."""
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(UTC).replace(tzinfo=None)


def as_utc(moment: dt.datetime) -> dt.datetime:
    """Attach UTC to a stored naive datetime (or convert an aware one)."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


@lru_cache(maxsize=8)
def _calendar(code: str) -> Any:
    return xcals.get_calendar(code)


@dataclass(frozen=True)
class MarketClock:
    market: str
    timezone: str
    now_local: dt.datetime
    is_open: bool
    last_completed_session: dt.date | None
    last_completed_close_utc: dt.datetime | None
    next_session: dt.date | None
    calendar_code: str
    calendar_valid_through: dt.date
    calendar_warning: str | None


class MarketCalendar:
    def __init__(self, market: str, config: MarketConfig, sessions: SessionsConfig) -> None:
        self.market = market
        self.config = config
        self.tz = ZoneInfo(config.timezone)
        self._sessions_config = sessions
        self._cal = _calendar(config.calendar)

    @property
    def valid_through(self) -> dt.date:
        """Last session the calendar library has data for."""
        return pd.Timestamp(self._cal.last_session).date()

    @property
    def valid_from(self) -> dt.date:
        return pd.Timestamp(self._cal.first_session).date()

    def sessions_between(self, start: dt.date, end: dt.date) -> list[dt.date]:
        """Trading sessions in start..end inclusive, clipped to the calendar's range."""
        low, high = max(start, self.valid_from), min(end, self.valid_through)
        if low > high:
            return []
        index = self._cal.sessions_in_range(pd.Timestamp(low), pd.Timestamp(high))
        return [pd.Timestamp(s).date() for s in index]

    def session_close_utc(self, session: dt.date) -> dt.datetime:
        close = pd.Timestamp(self._cal.session_close(pd.Timestamp(session)))
        return close.to_pydatetime().astimezone(UTC)

    def session_open_utc(self, session: dt.date) -> dt.datetime:
        open_ = pd.Timestamp(self._cal.session_open(pd.Timestamp(session)))
        return open_.to_pydatetime().astimezone(UTC)

    def last_completed_session(self, now: dt.datetime) -> dt.date | None:
        """Most recent session whose close plus the configured buffer has passed."""
        now = as_utc(now)
        buffer = dt.timedelta(minutes=self._sessions_config.close_buffer_minutes)
        local_today = now.astimezone(self.tz).date()
        candidates = self.sessions_between(local_today - dt.timedelta(days=30), local_today)
        for session in reversed(candidates):
            if self.session_close_utc(session) + buffer <= now:
                return session
        return None

    def is_open(self, now: dt.datetime) -> bool:
        now = as_utc(now)
        local_today = now.astimezone(self.tz).date()
        for session in self.sessions_between(local_today, local_today):
            if self.session_open_utc(session) <= now < self.session_close_utc(session):
                return True
        return False

    def next_session(self, now: dt.datetime) -> dt.date | None:
        now = as_utc(now)
        local_today = now.astimezone(self.tz).date()
        for session in self.sessions_between(local_today, local_today + dt.timedelta(days=30)):
            if self.session_open_utc(session) > now:
                return session
        return None

    def calendar_warning(self, now: dt.datetime) -> str | None:
        """Says so when the library has no (or little) future session data for this market."""
        today = as_utc(now).astimezone(self.tz).date()
        days_left = (self.valid_through - today).days
        if days_left < 0:
            return (
                f"The calendar library ({self.config.calendar}) has no session data after "
                f"{self.valid_through}; market status and freshness are unreliable."
            )
        if days_left <= self._sessions_config.calendar_end_warning_days:
            return (
                f"The calendar library ({self.config.calendar}) has holiday/session data only "
                f"through {self.valid_through}. Update exchange_calendars before then."
            )
        return None

    def clock(self, now: dt.datetime) -> MarketClock:
        now = as_utc(now)
        last = self.last_completed_session(now)
        return MarketClock(
            market=self.market,
            timezone=self.config.timezone,
            now_local=now.astimezone(self.tz),
            is_open=self.is_open(now),
            last_completed_session=last,
            last_completed_close_utc=self.session_close_utc(last) if last else None,
            next_session=self.next_session(now),
            calendar_code=self.config.calendar,
            calendar_valid_through=self.valid_through,
            calendar_warning=self.calendar_warning(now),
        )

    def candle_as_of_local(self, session: dt.date) -> dt.datetime | None:
        """When a daily candle became final: that session's close, in market time.
        None when the calendar does not list that date as a session."""
        if not self.sessions_between(session, session):
            return None
        return self.session_close_utc(session).astimezone(self.tz)
