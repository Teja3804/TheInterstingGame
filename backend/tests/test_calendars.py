"""Sessions, time zones and freshness. Dates are real calendar facts from the
exchange_calendars library (not market data)."""

from __future__ import annotations

import datetime as dt

import pytest

from app.config import Settings
from app.core import freshness
from tests.helpers import calendar_for, utc

D = dt.date


def test_session_counts_only_after_close_plus_buffer(settings: Settings) -> None:
    us = calendar_for(settings, "US")
    # Fri 8 Mar 2024: NYSE closes 16:00 EST = 21:00 UTC. Buffer is 30 minutes.
    assert us.last_completed_session(utc(2024, 3, 8, 21, 29)) == D(2024, 3, 7)
    assert us.last_completed_session(utc(2024, 3, 8, 21, 30)) == D(2024, 3, 8)


def test_daylight_saving_shifts_the_utc_close(settings: Settings) -> None:
    us = calendar_for(settings, "US")
    # Mon 11 Mar 2024 is after the US clock change: 16:00 EDT = 20:00 UTC.
    assert us.session_close_utc(D(2024, 3, 8)) == utc(2024, 3, 8, 21, 0)
    assert us.session_close_utc(D(2024, 3, 11)) == utc(2024, 3, 11, 20, 0)
    assert us.last_completed_session(utc(2024, 3, 11, 20, 29)) == D(2024, 3, 8)
    assert us.last_completed_session(utc(2024, 3, 11, 20, 30)) == D(2024, 3, 11)


def test_india_close_is_1530_ist(settings: Settings) -> None:
    india = calendar_for(settings, "IN")
    assert india.session_close_utc(D(2024, 3, 22)) == utc(2024, 3, 22, 10, 0)
    assert india.last_completed_session(utc(2024, 3, 22, 10, 29)) == D(2024, 3, 21)
    assert india.last_completed_session(utc(2024, 3, 22, 10, 30)) == D(2024, 3, 22)


def test_same_instant_is_a_different_local_day_per_market(settings: Settings) -> None:
    now = utc(2024, 3, 12, 1, 0)  # 21:00 Mon in New York, 06:30 Tue in Kolkata
    us, india = calendar_for(settings, "US").clock(now), calendar_for(settings, "IN").clock(now)
    assert us.now_local.date() == D(2024, 3, 11) and us.now_local.utcoffset() == dt.timedelta(
        hours=-4
    )
    assert india.now_local.date() == D(2024, 3, 12)
    assert india.now_local.utcoffset() == dt.timedelta(hours=5, minutes=30)
    assert us.last_completed_session == D(2024, 3, 11)
    assert india.last_completed_session == D(2024, 3, 11)  # Tuesday has not opened yet
    assert not us.is_open and not india.is_open


def test_weekends_and_holidays_are_not_sessions(settings: Settings) -> None:
    us, india = calendar_for(settings, "US"), calendar_for(settings, "IN")
    # 29 Mar 2024 is Good Friday (both closed); 25 Mar 2024 is Holi (India closed).
    assert us.sessions_between(D(2024, 3, 28), D(2024, 4, 1)) == [D(2024, 3, 28), D(2024, 4, 1)]
    assert D(2024, 3, 25) not in india.sessions_between(D(2024, 3, 22), D(2024, 3, 26))
    assert D(2024, 3, 25) in us.sessions_between(D(2024, 3, 22), D(2024, 3, 26))
    assert us.last_completed_session(utc(2024, 3, 29, 18, 0)) == D(2024, 3, 28)
    assert not us.is_open(utc(2024, 3, 29, 18, 0))
    assert us.is_open(utc(2024, 3, 28, 18, 0))


def test_early_close_is_respected(settings: Settings) -> None:
    us = calendar_for(settings, "US")
    # 3 Jul 2024: NYSE closes at 13:00 EDT = 17:00 UTC.
    assert us.session_close_utc(D(2024, 7, 3)) == utc(2024, 7, 3, 17, 0)
    assert us.last_completed_session(utc(2024, 7, 3, 17, 30)) == D(2024, 7, 3)
    assert us.last_completed_session(utc(2024, 7, 4, 23, 0)) == D(2024, 7, 3)  # 4 Jul holiday


def test_candle_as_of_is_the_session_close_in_market_time(settings: Settings) -> None:
    us, india = calendar_for(settings, "US"), calendar_for(settings, "IN")
    assert us.candle_as_of_local(D(2024, 3, 8)).isoformat() == "2024-03-08T16:00:00-05:00"  # type: ignore[union-attr]
    assert india.candle_as_of_local(D(2024, 3, 22)).isoformat() == "2024-03-22T15:30:00+05:30"  # type: ignore[union-attr]
    assert us.candle_as_of_local(D(2024, 3, 9)) is None  # Saturday: no session, no made-up time


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (utc(2024, 3, 8, 22, 0), freshness.FRESH),  # Friday evening
        (utc(2024, 3, 9, 15, 0), freshness.FRESH),  # Saturday: weekend is never stale
        (utc(2024, 3, 10, 15, 0), freshness.FRESH),  # Sunday
        (utc(2024, 3, 11, 15, 0), freshness.FRESH),  # Monday, session still in progress
        (utc(2024, 3, 11, 20, 30), freshness.STALE),  # Monday's session has completed
    ],
)
def test_stale_only_once_a_newer_session_has_completed(
    settings: Settings, now: dt.datetime, expected: str
) -> None:
    us = calendar_for(settings, "US")
    latest_stored = D(2024, 3, 8)
    assert freshness.classify(latest_stored, us.last_completed_session(now)) == expected


def test_holiday_does_not_make_data_stale(settings: Settings) -> None:
    us = calendar_for(settings, "US")
    good_friday_evening = utc(2024, 3, 29, 23, 0)
    assert (
        freshness.classify(D(2024, 3, 28), us.last_completed_session(good_friday_evening))
        == freshness.FRESH
    )


def test_missing_and_unknown() -> None:
    assert freshness.classify(None, D(2024, 3, 8)) == freshness.MISSING
    assert freshness.classify(D(2024, 3, 8), None) == freshness.UNKNOWN


def test_calendar_end_warning(settings: Settings) -> None:
    india = calendar_for(settings, "IN")
    end = india.valid_through
    far = dt.datetime.combine(end - dt.timedelta(days=200), dt.time(12), tzinfo=dt.UTC)
    near = dt.datetime.combine(end - dt.timedelta(days=10), dt.time(12), tzinfo=dt.UTC)
    past = dt.datetime.combine(end + dt.timedelta(days=5), dt.time(12), tzinfo=dt.UTC)
    assert india.calendar_warning(far) is None
    assert str(end) in (india.calendar_warning(near) or "")
    assert "no session data after" in (india.calendar_warning(past) or "")
