"""HTTP routes only. Business logic lives in app.services and app.core."""

from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_analysis, get_ingestion, get_research, get_settings_dep
from app.config import Settings
from app.core import freshness
from app.db import get_db
from app.services.analysis import AnalysisService, iso_utc, series_to_json
from app.services.calendars import MarketClock, utc_now
from app.services.ingestion import IngestionService
from app.services.research import ResearchService

router = APIRouter(prefix="/api")

SCHEDULER_NOTE = (
    "Scheduled monitoring is not active. Phase 1 has no scheduler: data changes only when "
    "a manual refresh is run."
)


def _scheduler() -> dict[str, Any]:
    return {"active": False, "last_successful_run_utc": None, "note": SCHEDULER_NOTE}


def _clock_json(clock: MarketClock) -> dict[str, Any]:
    return {
        "timezone": clock.timezone,
        "now_local": clock.now_local.isoformat(),
        "is_open": clock.is_open,
        "last_completed_session": (
            clock.last_completed_session.isoformat() if clock.last_completed_session else None
        ),
        "last_completed_close_utc": iso_utc(clock.last_completed_close_utc),
        "next_session": clock.next_session.isoformat() if clock.next_session else None,
        "calendar": clock.calendar_code,
        "calendar_valid_through": clock.calendar_valid_through.isoformat(),
        "calendar_warning": clock.calendar_warning,
    }


def _require_market(settings: Settings, symbol: str) -> str:
    market = settings.market_of(symbol)
    if market is None:
        raise HTTPException(404, f"{symbol} is not in config/watchlists.yaml")
    return market


@router.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "time_utc": iso_utc(utc_now()), "scheduler": _scheduler()}


@router.get("/sources/status")
def sources_status(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    analysis: AnalysisService = Depends(get_analysis),
) -> dict[str, Any]:
    now = utc_now()
    statuses = analysis.fetch_status(db)
    ranges = analysis.stored_ranges(db)
    issue_counts = analysis.issue_counts(db)

    markets: list[dict[str, Any]] = []
    symbols: list[dict[str, Any]] = []
    for code, market in settings.markets.items():
        clock = analysis.calendar(code).clock(now)
        counts = {
            freshness.FRESH: 0,
            freshness.STALE: 0,
            freshness.MISSING: 0,
            freshness.UNKNOWN: 0,
        }
        for symbol in market.every_symbol():
            stored = ranges.get(symbol)
            state = freshness.classify(stored[1] if stored else None, clock.last_completed_session)
            counts[state] += 1
            status = statuses.get(symbol)
            symbols.append(
                {
                    "symbol": symbol,
                    "market": code,
                    "is_benchmark": symbol in market.benchmarks,
                    "freshness": state,
                    "first_candle_date": stored[0].isoformat() if stored else None,
                    "latest_candle_date": stored[1].isoformat() if stored else None,
                    "stored_rows": stored[2] if stored else 0,
                    "last_attempt_utc": iso_utc(status.last_attempt_at) if status else None,
                    "last_success_utc": iso_utc(status.last_success_at) if status else None,
                    "last_error_utc": iso_utc(status.last_error_at) if status else None,
                    "last_error": status.last_error if status else None,
                    "last_outcome": status.last_outcome if status else None,
                    "last_rows_fetched": status.last_rows_fetched if status else None,
                    "quality_issue_count": issue_counts.get(symbol, 0),
                }
            )
        markets.append(
            {
                "code": code,
                "name": market.name,
                "currency": market.currency,
                "clock": _clock_json(clock),
                "freshness_counts": counts,
            }
        )

    successes = [s.last_success_at for s in statuses.values() if s.last_success_at]
    attempts = [s.last_attempt_at for s in statuses.values() if s.last_attempt_at]
    failing = [s.symbol for s in statuses.values() if s.last_outcome == "failed"]
    return {
        "generated_at_utc": iso_utc(now),
        "provider": {
            "name": settings.provider.name,
            "label": settings.provider.label,
            "data_kind": "delayed / end-of-day",
            "last_success_utc": iso_utc(max(successes)) if successes else None,
            "last_attempt_utc": iso_utc(max(attempts)) if attempts else None,
            "symbols_failing": sorted(failing),
        },
        "scheduler": _scheduler(),
        "markets": markets,
        "symbols": symbols,
    }


@router.get("/watchlists")
def watchlists(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    analysis: AnalysisService = Depends(get_analysis),
) -> dict[str, Any]:
    now = utc_now()
    out: list[dict[str, Any]] = []
    for code, market in settings.markets.items():
        calendar = analysis.calendar(code)
        clock = calendar.clock(now)
        benchmark_symbol = market.relative_strength_benchmark
        benchmark = analysis.load(db, benchmark_symbol, code)
        rows: list[dict[str, Any]] = []
        for symbol in [*market.symbols, *market.benchmarks]:
            data = benchmark if symbol == benchmark_symbol else analysis.load(db, symbol, code)
            versus = None if symbol == benchmark_symbol else benchmark_symbol
            values, reasons = analysis.snapshot(data, benchmark if versus else None, versus)
            profile = analysis.profile(db, symbol)
            row = analysis.provenance(data, calendar, clock.last_completed_session)
            row |= {
                "is_benchmark": symbol in market.benchmarks,
                "name": profile["name"] if profile else None,
                "relative_strength_benchmark": versus,
                "values": values,
                "unavailable": reasons,
            }
            if data.empty:
                row["unavailable_reason"] = "no data stored; run a manual refresh"
            rows.append(row)
        out.append(
            {
                "code": code,
                "name": market.name,
                "currency": market.currency,
                "timezone": market.timezone,
                "relative_strength_benchmark": benchmark_symbol,
                "relative_strength_window": settings.indicators.relative_strength_window,
                "clock": _clock_json(clock),
                "rows": rows,
            }
        )
    return {"generated_at_utc": iso_utc(now), "markets": out}


@router.get("/symbols/{symbol}/prices")
def prices(
    symbol: str,
    sessions: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    analysis: AnalysisService = Depends(get_analysis),
) -> dict[str, Any]:
    market = _require_market(settings, symbol)
    count = min(sessions or settings.api.default_price_sessions, settings.api.max_price_sessions)
    calendar = analysis.calendar(market)
    data = analysis.load(db, symbol, market)
    meta = analysis.provenance(data, calendar, calendar.last_completed_session(utc_now()))
    if data.empty:
        return meta | {"bars": [], "unavailable_reason": "no data stored; run a manual refresh"}
    frame = data.frame.tail(count)
    adjusted = data.adjusted.tail(count)
    fetched = [iso_utc(pd.Timestamp(v).to_pydatetime()) for v in frame["fetched_at"]]
    bars = [
        {
            "date": day.isoformat(),
            "open": float(frame["open"].iloc[i]),
            "high": float(frame["high"].iloc[i]),
            "low": float(frame["low"].iloc[i]),
            "close": float(frame["close"].iloc[i]),
            "adj_close": float(frame["adj_close"].iloc[i]),
            "adj_open": float(adjusted["open"].iloc[i]),
            "adj_high": float(adjusted["high"].iloc[i]),
            "adj_low": float(adjusted["low"].iloc[i]),
            "volume": float(frame["volume"].iloc[i]),
            "fetched_at_utc": fetched[i],
        }
        for i, day in enumerate(frame.index)
    ]
    return meta | {
        "price_note": (
            "close is split-adjusted as reported by the provider; adj_* are also "
            "dividend-adjusted and are what indicators use"
        ),
        "bars": bars,
    }


@router.get("/symbols/{symbol}/indicators")
def symbol_indicators(
    symbol: str,
    sessions: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    analysis: AnalysisService = Depends(get_analysis),
) -> dict[str, Any]:
    market = _require_market(settings, symbol)
    count = min(sessions or settings.api.default_price_sessions, settings.api.max_price_sessions)
    calendar = analysis.calendar(market)
    data = analysis.load(db, symbol, market)
    meta = analysis.provenance(data, calendar, calendar.last_completed_session(utc_now()))

    benchmark_symbol: str | None = settings.markets[market].relative_strength_benchmark
    if benchmark_symbol == symbol:
        benchmark_symbol = None
    benchmark = analysis.load(db, benchmark_symbol, market) if benchmark_symbol else None

    body: dict[str, Any] = meta | {
        "is_benchmark": settings.is_benchmark(symbol),
        "relative_strength_benchmark": benchmark_symbol,
        "parameters": settings.indicators.model_dump(),
        "profile": analysis.profile(db, symbol),
        "quality_issues": analysis.issues(db, symbol),
        "corporate_actions": analysis.actions(db, symbol),
    }
    if data.empty:
        return body | {
            "unavailable_reason": "no data stored; run a manual refresh",
            "snapshot": {},
            "unavailable": {},
            "series": {},
            "dates": [],
            "support": [],
            "resistance": [],
        }

    values, reasons = analysis.snapshot(data, benchmark, benchmark_symbol)
    series = analysis.indicator_series(data, benchmark)
    return body | {
        "snapshot": values,
        "unavailable": reasons,
        "dates": [d.isoformat() for d in data.frame.index[-count:]],
        "series": {name: series_to_json(column.tail(count)) for name, column in series.items()},
        **analysis.levels(data),
    }


@router.get("/stocks")
def stocks(
    db: Session = Depends(get_db), research: ResearchService = Depends(get_research)
) -> dict[str, Any]:
    """Screen 1 list: every watchlist stock with its score and rule-based suggestion."""
    return research.stocks(db, utc_now())


@router.get("/symbols/{symbol}/insight")
def symbol_insight(
    symbol: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    research: ResearchService = Depends(get_research),
) -> dict[str, Any]:
    """Screen 1 detail: score breakdown, trade plan, holder advice and hedge estimate."""
    _require_market(settings, symbol)
    body = research.insight(db, utc_now(), symbol)
    if body is None:
        raise HTTPException(404, f"{symbol} is a reference symbol and is not scored")
    return body


@router.get("/risk")
def risk_analysis(
    db: Session = Depends(get_db), research: ResearchService = Depends(get_research)
) -> dict[str, Any]:
    """Screen 2: BACKTEST risk analysis of the current strategy."""
    return research.risk(db, utc_now())


@router.get("/strategies")
def strategy_comparison(
    db: Session = Depends(get_db), research: ResearchService = Depends(get_research)
) -> dict[str, Any]:
    """Screen 3: BACKTEST comparison of alternative strategies with the current one."""
    return research.strategies(db, utc_now())


class IngestRequest(BaseModel):
    symbols: list[str] | None = None
    force: bool = False


@router.post("/ingest")
def ingest(
    request: IngestRequest | None = None,
    settings: Settings = Depends(get_settings_dep),
    ingestion: IngestionService = Depends(get_ingestion),
) -> dict[str, Any]:
    """Manual refresh. Runs synchronously; there is no scheduler in Phase 1."""
    request = request or IngestRequest()
    if request.symbols:
        unknown = [s for s in request.symbols if settings.market_of(s) is None]
        if unknown:
            raise HTTPException(404, f"not in config/watchlists.yaml: {', '.join(unknown)}")
    started = utc_now()
    results = ingestion.ingest_all(symbols=request.symbols, force=request.force)
    return {
        "started_utc": iso_utc(started),
        "finished_utc": iso_utc(utc_now()),
        "source": settings.provider.name,
        "fetched": sum(r.outcome == "fetched" for r in results),
        "cached": sum(r.outcome == "cached" for r in results),
        "failed": sum(r.outcome == "failed" for r in results),
        "results": [
            {
                "symbol": r.symbol,
                "market": r.market,
                "outcome": r.outcome,
                "rows_stored": r.rows_stored,
                "full_refetch": r.full_refetch,
                "partial_candles_dropped": r.partial_candles_dropped,
                "error": r.error,
                "warning_count": len(r.warnings),
            }
            for r in results
        ],
    }
