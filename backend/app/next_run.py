"""Print how long the publishing workflow should wait before its next run.

    python -m app.next_run --started 2026-11-20T20:07:24Z

Prints `seconds=<n>` and `reason=<text>` lines (the format of $GITHUB_OUTPUT).
"""

from __future__ import annotations

import argparse
import datetime as dt

from app.config import get_settings
from app.services.calendars import MarketCalendar, as_utc, utc_now
from app.services.schedule import next_run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--started", required=True, help="when this run started (ISO 8601)")
    args = parser.parse_args()

    settings = get_settings()
    started = as_utc(dt.datetime.fromisoformat(args.started.replace("Z", "+00:00")))
    now = utc_now()
    calendars = [
        MarketCalendar(code, market, settings.sessions) for code, market in settings.markets.items()
    ]
    plan = next_run(
        calendars,
        now=now,
        started=started,
        every=dt.timedelta(minutes=settings.site.update_every_minutes),
        idle_max=dt.timedelta(minutes=settings.site.idle_max_minutes),
        close_buffer=dt.timedelta(minutes=settings.sessions.close_buffer_minutes),
    )
    print(f"seconds={max(0, round((plan.at - now).total_seconds()))}")
    print(f"at={plan.at.isoformat().replace('+00:00', 'Z')}")
    print(f"reason={plan.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
