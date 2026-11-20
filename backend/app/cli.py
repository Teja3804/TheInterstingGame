"""Refresh from the command line.

    python -m app.cli [--force] [--no-quotes | --quotes-only] [SYMBOL ...]

Fetches completed daily candles, then the latest delayed price for every watchlist stock and
benchmark. The scheduled GitHub workflow runs this before publishing the site."""

from __future__ import annotations

import argparse
import logging

from app.api.deps import get_ingestion, get_quotes
from app.db import init_db


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch daily history and latest prices.")
    parser.add_argument("symbols", nargs="*", help="limit to these symbols (default: all)")
    parser.add_argument("--force", action="store_true", help="ignore the cache; full re-download")
    which = parser.add_mutually_exclusive_group()
    which.add_argument("--no-quotes", action="store_true", help="daily candles only")
    which.add_argument("--quotes-only", action="store_true", help="latest prices only")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    init_db()
    failed_history: list[str] = []
    if not args.quotes_only:
        failed_history = _history(args.symbols, args.force)
    failed_quotes: list[str] = []
    if not args.no_quotes:
        run = get_quotes().refresh()
        for symbol, error in run.errors.items():
            print(f"quote {symbol:<14} failed   {error}")
        for symbol, warnings in run.warnings.items():
            print(f"quote {symbol:<14} warning  {'; '.join(warnings)}")
        print(f"quotes: {run.fetched} ok, {run.failed} failed")
        failed_quotes = list(run.errors)
    return 1 if failed_history or failed_quotes else 0


def _history(symbols: list[str], force: bool) -> list[str]:
    results = get_ingestion().ingest_all(symbols=symbols or None, force=force)
    for result in results:
        detail = result.error or f"{result.rows_stored} rows, {len(result.warnings)} warnings"
        print(f"{result.symbol:<14} {result.market:<3} {result.outcome:<8} {detail}")
    failed = [r.symbol for r in results if r.outcome == "failed"]
    print(
        f"\n{len(results) - len(failed)} ok, {len(failed)} failed"
        + (f": {failed}" if failed else "")
    )
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
