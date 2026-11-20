"""Latest delayed prices: fetched through a provider, checked, stored and served."""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import MarketConfig, Settings
from app.core import quotes as checks
from app.models import LatestQuote, PriceBar
from app.providers.base import MarketDataProvider, ProviderError
from app.services.calendars import MarketCalendar, as_utc, to_naive_utc, utc_now

logger = logging.getLogger(__name__)


def iso(moment: dt.datetime | None) -> str | None:
    return as_utc(moment).isoformat().replace("+00:00", "Z") if moment else None


def quote_symbols(market: MarketConfig) -> list[str]:
    """Watchlist stocks, then benchmarks: what the screens show a latest price for."""
    return list(dict.fromkeys([*market.symbols, *market.benchmarks]))


@dataclass
class QuoteRun:
    fetched: int = 0
    failed: int = 0
    errors: dict[str, str] = field(default_factory=dict)
    warnings: dict[str, list[str]] = field(default_factory=dict)


class QuoteService:
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

    def _calendar(self, code: str) -> MarketCalendar:
        return MarketCalendar(code, self._settings.markets[code], self._settings.sessions)

    # -- refresh -----------------------------------------------------------------------

    def refresh(self, markets: list[str] | None = None) -> QuoteRun:
        run = QuoteRun()
        for code, market in self._settings.markets.items():
            if markets is not None and code not in markets:
                continue
            calendar = self._calendar(code)
            for symbol in quote_symbols(market):
                with self._session_factory() as db:
                    error, warnings = self._refresh_one(db, code, market, calendar, symbol)
                    db.commit()
                if error is None:
                    run.fetched += 1
                    if warnings:
                        run.warnings[symbol] = warnings
                else:
                    run.failed += 1
                    run.errors[symbol] = error
        return run

    def _row(self, db: Session, code: str, symbol: str) -> LatestQuote:
        row = db.scalar(
            select(LatestQuote).where(
                LatestQuote.symbol == symbol, LatestQuote.source == self._provider.name
            )
        )
        if row is None:
            row = LatestQuote(symbol=symbol, market=code, source=self._provider.name)
            db.add(row)
        return row

    def _stored_close(self, db: Session, symbol: str, session: dt.date) -> float | None:
        return db.scalar(
            select(PriceBar.close).where(
                PriceBar.symbol == symbol,
                PriceBar.source == self._provider.name,
                PriceBar.date == session,
            )
        )

    def _refresh_one(
        self,
        db: Session,
        code: str,
        market: MarketConfig,
        calendar: MarketCalendar,
        symbol: str,
    ) -> tuple[str | None, list[str]]:
        now = self._now()
        row = self._row(db, code, symbol)
        try:
            raw = self._provider.fetch_quote(symbol)
        except ProviderError as exc:
            message = str(exc)
        except Exception as exc:  # never let one symbol stop the run
            message = f"{type(exc).__name__}: {exc}"
        else:
            session = raw.market_time.astimezone(calendar.tz).date()
            reference = checks.previous_close(raw.daily_closes, session)
            result = checks.check_quote(
                price=raw.price,
                market_time_utc=as_utc(raw.market_time),
                currency=raw.currency,
                expected_currency=market.currency,
                reference_close=reference,
                stored_close_same_session=self._stored_close(db, symbol, session),
                now_utc=as_utc(now),
                max_future_seconds=self._settings.quotes.max_future_seconds,
                suspicious_move_pct=self._settings.data_quality.suspicious_move_pct,
                close_match_tolerance_pct=self._settings.quotes.close_match_tolerance_pct,
            )
            if result.usable:
                row.market = code
                row.price = raw.price
                row.previous_close = reference
                row.currency = raw.currency
                row.market_time = to_naive_utc(raw.market_time)
                row.fetched_at = to_naive_utc(now)
                row.warnings = "\n".join(result.warnings) or None
                row.last_error = None
                row.last_error_at = None
                return None, result.warnings
            message = f"{symbol}: quote rejected ({'; '.join(result.warnings)})"
        logger.warning("quote failed for %s: %s", symbol, message)
        row.market = code
        row.last_error = message
        row.last_error_at = to_naive_utc(now)
        return message, []

    # -- read --------------------------------------------------------------------------

    def payload(self, db: Session, now: dt.datetime) -> dict[str, Any]:
        stored = db.scalars(select(LatestQuote).where(LatestQuote.source == self._provider.name))
        rows = {r.symbol: r for r in stored}
        markets: list[dict[str, Any]] = []
        for code, market in self._settings.markets.items():
            calendar = self._calendar(code)
            is_open = calendar.is_open(now)
            today = as_utc(now).astimezone(calendar.tz).date()
            items: list[dict[str, Any]] = []
            for symbol in quote_symbols(market):
                row = rows.get(symbol)
                item: dict[str, Any] = {
                    "symbol": symbol,
                    "is_benchmark": symbol in market.benchmarks,
                    "currency": market.currency,
                }
                if row is None or row.price is None or row.market_time is None:
                    item |= {
                        "price": None,
                        "unavailable_reason": (
                            row.last_error
                            if row is not None and row.last_error
                            else "no quote fetched yet"
                        ),
                    }
                    items.append(item)
                    continue
                local = as_utc(row.market_time).astimezone(calendar.tz)
                during = is_open and local.date() == today
                item |= {
                    "price": row.price,
                    "provider_currency": row.currency,
                    "previous_close": row.previous_close,
                    "change_pct": checks.change_pct(row.price, row.previous_close),
                    "kind": checks.DURING_SESSION if during else checks.AFTER_CLOSE,
                    "market_time_utc": iso(row.market_time),
                    "market_time_local": local.isoformat(),
                    "fetched_at_utc": iso(row.fetched_at),
                    "warnings": row.warnings.split("\n") if row.warnings else [],
                    "last_error": row.last_error,
                    "last_error_utc": iso(row.last_error_at),
                }
                items.append(item)
            markets.append(
                {
                    "code": code,
                    "name": market.name,
                    "currency": market.currency,
                    "timezone": market.timezone,
                    "is_open": is_open,
                    "quotes": items,
                }
            )
        return {
            "generated_at_utc": iso(now),
            "source": self._provider.name,
            "source_label": self._settings.provider.label,
            "note": (
                "Latest prices are delayed (often by about 15 minutes) and come from Yahoo "
                "Finance. Indicators, scores and suggestions use completed daily candles only."
            ),
            "markets": markets,
        }
