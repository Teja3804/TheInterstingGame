"""Manual refresh from the command line: python -m app.cli [--force] [SYMBOL ...]"""

from __future__ import annotations

import argparse
import logging

from app.api.deps import get_ingestion
from app.db import init_db


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch daily history for the watchlists.")
    parser.add_argument("symbols", nargs="*", help="limit to these symbols (default: all)")
    parser.add_argument("--force", action="store_true", help="ignore the cache; full re-download")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    init_db()
    results = get_ingestion().ingest_all(symbols=args.symbols or None, force=args.force)
    for result in results:
        detail = result.error or f"{result.rows_stored} rows, {len(result.warnings)} warnings"
        print(f"{result.symbol:<14} {result.market:<3} {result.outcome:<8} {detail}")
    failed = [r.symbol for r in results if r.outcome == "failed"]
    print(
        f"\n{len(results) - len(failed)} ok, {len(failed)} failed"
        + (f": {failed}" if failed else "")
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
