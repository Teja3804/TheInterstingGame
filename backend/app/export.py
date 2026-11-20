"""Writes every screen's data as JSON files, for the hosted read-only snapshot.

    python -m app.export OUTPUT_DIR [--sessions 260] [--scheduled]

The files hold exactly what the API would return at the moment of export. `--scheduled` marks
the export as made by the scheduled GitHub workflow that republishes the website.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from app.api import routes
from app.api.deps import get_analysis, get_quotes, get_research
from app.config import get_settings
from app.db import get_session_factory, init_db
from app.services.analysis import iso_utc
from app.services.calendars import utc_now


def safe_name(symbol: str) -> str:
    """File-system and URL safe form of a symbol: ^GSPC -> _GSPC, M&M.NS -> M_M.NS."""
    return re.sub(r"[^A-Za-z0-9.-]", "_", symbol)


def _write(path: Path, body: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, separators=(",", ":"), allow_nan=False), encoding="utf-8")


def export(output: Path, sessions: int, scheduled: bool = False) -> int:
    settings, analysis, research = get_settings(), get_analysis(), get_research()
    init_db()
    with get_session_factory()() as db:
        status = routes.sources_status(db, settings, analysis)
        site = settings.site
        status["snapshot"] = {
            "exported_at_utc": iso_utc(utc_now()),
            "scheduled": scheduled,
            "update_every_minutes": site.update_every_minutes if scheduled else None,
            "stale_after_minutes": site.stale_after_minutes if scheduled else None,
            "note": (
                "Updated by a scheduled GitHub job about every "
                f"{site.update_every_minutes} minutes while a market is open. "
                "Figures are as of the update time shown."
                if scheduled
                else "Read-only snapshot. Figures are as of the export time shown."
            ),
        }
        _write(output / "status.json", status)
        _write(output / "quotes.json", get_quotes().payload(db, utc_now()))
        _write(output / "stocks.json", routes.stocks(db, research))
        _write(output / "risk.json", routes.risk_analysis(db, research))
        _write(output / "strategies.json", routes.strategy_comparison(db, research))
        count = 5
        for market in settings.markets.values():
            for symbol in market.symbols:
                body = {
                    "prices": routes.prices(symbol, sessions, db, settings, analysis),
                    "indicators": routes.symbol_indicators(
                        symbol, sessions, db, settings, analysis
                    ),
                    "insight": routes.symbol_insight(symbol, db, settings, research),
                }
                _write(output / "symbols" / f"{safe_name(symbol)}.json", body)
                count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a read-only JSON snapshot.")
    parser.add_argument("output", type=Path)
    parser.add_argument("--sessions", type=int, default=260, help="chart history per symbol")
    parser.add_argument(
        "--scheduled", action="store_true", help="made by the scheduled publishing workflow"
    )
    args = parser.parse_args()
    count = export(args.output, args.sessions, args.scheduled)
    print(f"wrote {count} files to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
