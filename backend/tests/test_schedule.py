"""When the publishing workflow runs next. Times are UTC; sessions come from the real
calendar library: Wed 6 Mar 2024, NYSE 14:30-21:00 UTC, BSE 03:45-10:00 UTC."""

from __future__ import annotations

import datetime as dt

import pytest

from app.config import Settings
from app.services.schedule import NextRun, next_run
from tests.helpers import calendar_for, utc

EVERY = dt.timedelta(minutes=15)
IDLE = dt.timedelta(minutes=120)


def plan(settings: Settings, now: dt.datetime, started: dt.datetime | None = None) -> NextRun:
    calendars = [calendar_for(settings, "US"), calendar_for(settings, "IN")]
    buffer = dt.timedelta(minutes=settings.sessions.close_buffer_minutes)
    return next_run(calendars, now, started or now, EVERY, IDLE, buffer)


def test_during_a_session_the_next_run_is_one_interval_after_this_one_started(
    settings: Settings,
) -> None:
    result = plan(settings, utc(2024, 3, 6, 18, 0), started=utc(2024, 3, 6, 17, 56))
    assert result.at == utc(2024, 3, 6, 18, 11)
    assert result.reason == "session active: US"


def test_a_run_longer_than_the_interval_is_followed_at_once(settings: Settings) -> None:
    result = plan(settings, utc(2024, 3, 6, 18, 0), started=utc(2024, 3, 6, 17, 40))
    assert result.at == utc(2024, 3, 6, 18, 0)


def test_india_session_is_active(settings: Settings) -> None:
    assert plan(settings, utc(2024, 3, 6, 5, 0)).reason == "session active: IN"


def test_runs_continue_until_one_lands_after_the_close_buffer(settings: Settings) -> None:
    buffer = settings.sessions.close_buffer_minutes
    close = utc(2024, 3, 6, 21, 0)
    last_active = close + dt.timedelta(minutes=buffer) + EVERY - dt.timedelta(minutes=1)
    assert plan(settings, last_active).reason == "session active: US"
    assert plan(settings, last_active + dt.timedelta(minutes=2)).reason.startswith("markets")


def test_while_closed_it_waits_at_most_the_idle_limit(settings: Settings) -> None:
    now = utc(2024, 3, 6, 22, 30)  # India opens 03:45 UTC, more than 2 hours away
    result = plan(settings, now)
    assert result.at == now + IDLE
    assert result.reason == "markets closed: idle check"


def test_while_closed_it_wakes_for_the_next_open(settings: Settings) -> None:
    result = plan(settings, utc(2024, 3, 7, 2, 30))
    assert result.at == utc(2024, 3, 7, 3, 45)
    assert result.reason == "next session opens: IN"


@pytest.mark.parametrize("hour", [0, 12, 23])
def test_weekend_is_idle(settings: Settings, hour: int) -> None:
    now = utc(2024, 3, 9, hour, 0)  # Saturday
    assert plan(settings, now).at == now + IDLE
