"""Fetches daily history through a provider, validates it and stores it."""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.core import quality
from app.core.quality import Issue
from app.models import CorporateAction, DataQualityIssue, FetchStatus, PriceBar, SymbolProfile
from app.providers.base import (
    MarketDataProvider,
    PriceHistory,
    ProviderError,
    RawAction,
    RawBar,
)
from app.services.calendars import MarketCalendar, to_naive_utc, utc_now

logger = logging.getLogger(__name__)

OUTCOME_FETCHED = "fetched"
OUTCOME_CACHED = "cached"
OUTCOME_FAILED = "failed"

PROFILE_UNAVAILABLE = "profile_unavailable"


def is_index_symbol(symbol: str) -> bool:
    """Yahoo index symbols start with a caret. Indices may report zero volume."""
    return symbol.startswith("^")


@dataclass
class IngestResult:
    symbol: str
    market: str
    outcome: str
    rows_stored: int = 0
    full_refetch: bool = False
    partial_candles_dropped: int = 0
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


class IngestionService:
    def __init__(
        self,
        settings: Settings,
        provider: MarketDataProvider,
        session_factory: sessionmaker[Session],
        now: Callable[[], dt.datetime] = utc_now,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._session_factory = session_factory
        self._now = now

    # -- public ------------------------------------------------------------------------

    def ingest_all(
        self, symbols: list[str] | None = None, force: bool = False
    ) -> list[IngestResult]:
        wanted = set(symbols) if symbols else None
        results: list[IngestResult] = []
        for market, symbol in self._settings.all_symbols():
            if wanted is not None and symbol not in wanted:
                continue
            results.append(self.ingest_symbol(market, symbol, force=force))
        return results

    def ingest_symbol(self, market: str, symbol: str, force: bool = False) -> IngestResult:
        with self._session_factory() as db:
            try:
                result = self._ingest(db, market, symbol, force)
                db.commit()
                return result
            except Exception as exc:  # record every failure; never stop the whole run
                db.rollback()
                message = (
                    str(exc) if isinstance(exc, ProviderError) else f"{type(exc).__name__}: {exc}"
                )
                logger.warning("ingest failed for %s: %s", symbol, message)
                now = to_naive_utc(self._now())
                status = self._status(db, market, symbol)
                status.last_attempt_at = now
                status.last_error_at = now
                status.last_error = message
                status.last_outcome = OUTCOME_FAILED
                db.commit()
                return IngestResult(symbol, market, OUTCOME_FAILED, error=message)

    # -- internals ---------------------------------------------------------------------

    def _status(self, db: Session, market: str, symbol: str) -> FetchStatus:
        source = self._provider.name
        status = db.scalar(
            select(FetchStatus).where(FetchStatus.symbol == symbol, FetchStatus.source == source)
        )
        if status is None:
            status = FetchStatus(symbol=symbol, market=market, source=source)
            db.add(status)
        return status

    def _stored_range(self, db: Session, symbol: str) -> tuple[dt.date | None, dt.date | None]:
        row = db.execute(
            select(func.min(PriceBar.date), func.max(PriceBar.date)).where(
                PriceBar.symbol == symbol, PriceBar.source == self._provider.name
            )
        ).one()
        return row[0], row[1]

    def _stored_actions(self, db: Session, symbol: str) -> set[tuple[dt.date, str]]:
        rows = db.execute(
            select(CorporateAction.date, CorporateAction.action_type).where(
                CorporateAction.symbol == symbol, CorporateAction.source == self._provider.name
            )
        ).all()
        return {(r[0], r[1]) for r in rows}

    def _ingest(self, db: Session, market: str, symbol: str, force: bool) -> IngestResult:
        cfg = self._settings.provider
        now = self._now()
        now_naive = to_naive_utc(now)
        calendar = MarketCalendar(market, self._settings.markets[market], self._settings.sessions)
        last_completed = calendar.last_completed_session(now)
        if last_completed is None:
            raise ProviderError(
                f"{symbol}: the {market} calendar has no completed session near {now.date()}"
            )

        status = self._status(db, market, symbol)
        history_start = last_completed - dt.timedelta(days=366 * cfg.history_years)
        first_expected = next(
            iter(calendar.sessions_between(history_start, last_completed)), history_start
        )
        earliest, latest = self._stored_range(db, symbol)

        has_full_history = (
            earliest is not None
            and (earliest - first_expected).days <= cfg.incremental_overlap_days
        )
        if (
            not force
            and latest is not None
            and latest >= last_completed
            and has_full_history
            and status.last_success_at is not None
            and (now_naive - status.last_success_at) <= dt.timedelta(minutes=cfg.cache_ttl_minutes)
        ):
            status.last_attempt_at = now_naive
            status.last_outcome = OUTCOME_CACHED
            return IngestResult(symbol, market, OUTCOME_CACHED)

        full = force or latest is None or not has_full_history
        # A full download also covers anything already stored from before the window, so
        # every stored row carries the same adjustment basis.
        full_start = min(history_start, earliest) if earliest is not None else history_start
        start = (
            full_start
            if full or latest is None
            else latest - dt.timedelta(days=cfg.incremental_overlap_days)
        )
        history = self._provider.fetch_daily_history(symbol, start, last_completed)

        # Adjusted history changes whenever a new split or dividend appears, so the stored
        # adj_close values would no longer line up with new ones: re-download everything.
        known_actions = self._stored_actions(db, symbol)
        new_actions = [a for a in history.actions if (a.date, a.action_type) not in known_actions]
        if not full and new_actions:
            full = True
            history = self._provider.fetch_daily_history(symbol, full_start, last_completed)

        completed, dropped = quality.drop_incomplete(history.bars, last_completed)
        valid, issues = quality.validate_bars(completed, is_index=is_index_symbol(symbol))
        if not valid:
            raise ProviderError(f"{symbol}: provider returned no usable completed candles")
        issues.extend(
            Issue(quality.PARTIAL_CANDLE, "in-progress candle excluded", bar.date)
            for bar in dropped
        )

        self._upsert_bars(db, market, symbol, valid, now_naive)
        self._upsert_actions(db, market, symbol, history, last_completed, now_naive)
        db.flush()
        issues = [i for i in issues if i.kind != quality.ZERO_VOLUME]
        issues.extend(self._stored_data_issues(db, calendar, symbol, last_completed))
        issues.extend(self._refresh_profile(db, market, symbol, now_naive))
        self._replace_issues(db, symbol, issues, now_naive)

        status.last_attempt_at = now_naive
        status.last_success_at = now_naive
        status.last_rows_fetched = len(valid)
        status.last_outcome = OUTCOME_FETCHED
        status.last_error = None
        return IngestResult(
            symbol,
            market,
            OUTCOME_FETCHED,
            rows_stored=len(valid),
            full_refetch=full,
            partial_candles_dropped=len(dropped),
            warnings=[f"{i.kind}: {i.date or ''} {i.detail}".strip() for i in issues],
        )

    def _upsert_bars(
        self, db: Session, market: str, symbol: str, bars: list[RawBar], fetched_at: dt.datetime
    ) -> None:
        """Unique on symbol + date + source: existing rows are updated in place."""
        source = self._provider.name
        dates = [b.date for b in bars]
        existing = {
            row.date: row
            for row in db.scalars(
                select(PriceBar).where(
                    PriceBar.symbol == symbol,
                    PriceBar.source == source,
                    PriceBar.date >= min(dates),
                    PriceBar.date <= max(dates),
                )
            )
        }
        for bar in bars:
            row = existing.get(bar.date)
            if row is None:
                row = PriceBar(symbol=symbol, source=source, date=bar.date)
                db.add(row)
            row.market = market
            row.open, row.high, row.low = bar.open, bar.high, bar.low
            row.close, row.adj_close, row.volume = bar.close, bar.adj_close, bar.volume
            row.fetched_at = fetched_at

    def _upsert_actions(
        self,
        db: Session,
        market: str,
        symbol: str,
        history: PriceHistory,
        last_completed: dt.date,
        fetched_at: dt.datetime,
    ) -> None:
        source = self._provider.name
        existing = {
            (row.date, row.action_type): row
            for row in db.scalars(
                select(CorporateAction).where(
                    CorporateAction.symbol == symbol, CorporateAction.source == source
                )
            )
        }
        latest_by_key: dict[tuple[dt.date, str], RawAction] = {
            (a.date, a.action_type): a for a in history.actions if a.date <= last_completed
        }
        for key, action in latest_by_key.items():
            row = existing.get(key)
            if row is None:
                row = CorporateAction(
                    symbol=symbol, source=source, date=action.date, action_type=action.action_type
                )
                db.add(row)
            row.market = market
            row.value = action.value
            row.fetched_at = fetched_at

    def _stored_data_issues(
        self, db: Session, calendar: MarketCalendar, symbol: str, last_completed: dt.date
    ) -> list[Issue]:
        """Checks that need the whole stored series, not just the latest download."""
        source = self._provider.name
        rows = list(
            db.scalars(
                select(PriceBar)
                .where(PriceBar.symbol == symbol, PriceBar.source == source)
                .order_by(PriceBar.date)
            )
        )
        bars = [RawBar(r.date, r.open, r.high, r.low, r.close, r.adj_close, r.volume) for r in rows]
        split_dates = [d for d, kind in self._stored_actions(db, symbol) if kind == "split"]
        cfg = self._settings.data_quality
        issues = quality.find_suspicious_moves(bars, split_dates, cfg.suspicious_move_pct)
        if not is_index_symbol(symbol):
            issues.extend(
                Issue(quality.ZERO_VOLUME, "zero volume on a trading session", b.date)
                for b in bars
                if b.volume == 0
            )
        window_start = last_completed - dt.timedelta(days=cfg.missing_session_lookback_days)
        expected = calendar.sessions_between(window_start, last_completed)
        stored_dates = [b.date for b in bars]
        issues.extend(
            Issue(quality.MISSING_SESSION, "calendar session with no stored candle", d)
            for d in quality.find_missing_sessions(stored_dates, expected)
        )
        issues.extend(
            Issue(
                quality.UNEXPECTED_SESSION,
                "candle stored on a date the calendar library does not list as a session",
                d,
            )
            for d in quality.find_unexpected_sessions(stored_dates, expected)
        )
        return issues

    def _refresh_profile(
        self, db: Session, market: str, symbol: str, now_naive: dt.datetime
    ) -> list[Issue]:
        source = self._provider.name
        row = db.scalar(
            select(SymbolProfile).where(
                SymbolProfile.symbol == symbol, SymbolProfile.source == source
            )
        )
        ttl = dt.timedelta(days=self._settings.provider.profile_ttl_days)
        if row is not None and now_naive - row.fetched_at <= ttl:
            return []
        try:
            profile = self._provider.fetch_profile(symbol)
        except ProviderError as exc:
            return [Issue(PROFILE_UNAVAILABLE, f"profile could not be fetched: {exc}")]
        if row is None:
            row = SymbolProfile(symbol=symbol, source=source)
            db.add(row)
        row.market = market
        row.name, row.sector, row.industry = profile.name, profile.sector, profile.industry
        row.exchange, row.currency = profile.exchange, profile.currency
        row.quote_type = profile.quote_type
        row.fetched_at = now_naive
        return []

    def _replace_issues(
        self, db: Session, symbol: str, issues: list[Issue], now_naive: dt.datetime
    ) -> None:
        source = self._provider.name
        db.execute(
            delete(DataQualityIssue).where(
                DataQualityIssue.symbol == symbol, DataQualityIssue.source == source
            )
        )
        for issue in issues:
            db.add(
                DataQualityIssue(
                    symbol=symbol,
                    source=source,
                    date=issue.date,
                    kind=issue.kind,
                    detail=issue.detail,
                    detected_at=now_naive,
                )
            )
