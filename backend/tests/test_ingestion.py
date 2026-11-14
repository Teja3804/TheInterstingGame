"""Ingestion against a temporary SQLite database and an in-memory provider."""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.core import quality
from app.db import Base, make_engine
from app.models import CorporateAction, DataQualityIssue, FetchStatus, PriceBar, SymbolProfile
from app.providers.base import ProviderError, RawAction, RawBar, SymbolNotFoundError
from app.services.ingestion import IngestionService
from tests.helpers import FakeProvider, bars_on_sessions, calendar_for, utc

D = dt.date
SATURDAY = utc(2024, 3, 9, 12, 0)  # last completed US session: Fri 8 Mar 2024
LAST = D(2024, 3, 8)


class Clock:
    def __init__(self, now: dt.datetime) -> None:
        self.now = now

    def __call__(self) -> dt.datetime:
        return self.now


@pytest.fixture
def factory(tmp_path: Path) -> sessionmaker[Session]:
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def us_bars(settings: Settings, daily: pd.DataFrame, end: dt.date = LAST) -> list[RawBar]:
    start = LAST - dt.timedelta(days=366 * settings.provider.history_years)
    return bars_on_sessions(daily, calendar_for(settings, "US").sessions_between(start, end))


def make_service(
    settings: Settings,
    factory: sessionmaker[Session],
    provider: FakeProvider,
    now: dt.datetime = SATURDAY,
) -> tuple[IngestionService, Clock]:
    clock = Clock(now)
    return IngestionService(settings, provider, factory, now=clock), clock


def count(factory: sessionmaker[Session], symbol: str) -> int:
    with factory() as db:
        return int(
            db.scalar(select(func.count()).select_from(PriceBar).where(PriceBar.symbol == symbol))
            or 0
        )


def issues(factory: sessionmaker[Session], symbol: str) -> list[tuple[str, dt.date | None]]:
    with factory() as db:
        rows = db.scalars(select(DataQualityIssue).where(DataQualityIssue.symbol == symbol))
        return sorted(((r.kind, r.date) for r in rows), key=str)


def test_first_ingest_stores_two_years_with_provenance(settings, factory, daily) -> None:  # type: ignore[no-untyped-def]
    bars = us_bars(settings, daily)
    provider = FakeProvider(bars={"AAPL": bars})
    service, _ = make_service(settings, factory, provider)
    result = service.ingest_symbol("US", "AAPL")

    assert result.outcome == "fetched" and result.full_refetch and result.rows_stored == len(bars)
    assert len(bars) >= 500  # at least two years of sessions
    assert provider.calls == [("AAPL", LAST - dt.timedelta(days=732), LAST)]
    with factory() as db:
        row = db.scalars(
            select(PriceBar).where(PriceBar.symbol == "AAPL").order_by(PriceBar.date.desc())
        ).first()
        assert row is not None
        assert (row.date, row.market, row.source) == (LAST, "US", "fake")
        assert row.close == bars[-1].close and row.adj_close == bars[-1].adj_close
        assert row.fetched_at == SATURDAY.replace(tzinfo=None)  # stored as naive UTC
        status = db.scalars(select(FetchStatus).where(FetchStatus.symbol == "AAPL")).one()
        assert status.last_outcome == "fetched" and status.last_error is None
        assert status.last_rows_fetched == len(bars)
        profile = db.scalars(select(SymbolProfile).where(SymbolProfile.symbol == "AAPL")).one()
        assert profile.name == "Synthetic AAPL"
    assert issues(factory, "AAPL") == []


def test_fresh_data_is_served_from_cache(settings, factory, daily) -> None:  # type: ignore[no-untyped-def]
    provider = FakeProvider(bars={"AAPL": us_bars(settings, daily)})
    service, clock = make_service(settings, factory, provider)
    service.ingest_symbol("US", "AAPL")
    clock.now += dt.timedelta(minutes=settings.provider.cache_ttl_minutes - 1)
    assert service.ingest_symbol("US", "AAPL").outcome == "cached"
    assert len(provider.calls) == 1 and provider.profile_calls == ["AAPL"]


def test_refetch_updates_in_place_without_duplicates(settings, factory, daily) -> None:  # type: ignore[no-untyped-def]
    bars = us_bars(settings, daily)
    provider = FakeProvider(bars={"AAPL": bars})
    service, clock = make_service(settings, factory, provider)
    service.ingest_symbol("US", "AAPL")
    before = count(factory, "AAPL")

    # The provider revises the last candle; the cache has expired.
    provider.bars["AAPL"] = [
        *bars[:-1],
        replace(bars[-1], close=bars[-1].close + 1, adj_close=bars[-1].adj_close + 1),
    ]
    clock.now += dt.timedelta(minutes=settings.provider.cache_ttl_minutes + 1)
    result = service.ingest_symbol("US", "AAPL")

    assert result.outcome == "fetched" and not result.full_refetch
    assert count(factory, "AAPL") == before  # unique on symbol + date + source
    overlap = settings.provider.incremental_overlap_days
    assert provider.calls[-1] == ("AAPL", LAST - dt.timedelta(days=overlap), LAST)
    with factory() as db:
        row = db.scalars(
            select(PriceBar).where(PriceBar.symbol == "AAPL", PriceBar.date == LAST)
        ).one()
        assert row.close == bars[-1].close + 1
        assert row.fetched_at == clock.now.replace(tzinfo=None)


def test_provider_duplicates_are_stored_once(settings, factory, daily) -> None:  # type: ignore[no-untyped-def]
    bars = us_bars(settings, daily)
    provider = FakeProvider(bars={"AAPL": [*bars, bars[-1]]})
    service, _ = make_service(settings, factory, provider)
    service.ingest_symbol("US", "AAPL")
    assert count(factory, "AAPL") == len(bars)
    assert (quality.DUPLICATE_ROW, LAST) in issues(factory, "AAPL")


def test_in_progress_candle_is_not_stored(settings, factory, daily) -> None:  # type: ignore[no-untyped-def]
    monday = D(2024, 3, 11)
    provider = FakeProvider(bars={"AAPL": us_bars(settings, daily, end=monday)})
    during_session = utc(2024, 3, 11, 15, 0)  # 11:00 in New York
    service, _ = make_service(settings, factory, provider, now=during_session)
    result = service.ingest_symbol("US", "AAPL")

    assert result.partial_candles_dropped == 1
    with factory() as db:
        assert db.scalar(select(func.max(PriceBar.date))) == LAST
    assert (quality.PARTIAL_CANDLE, monday) in issues(factory, "AAPL")

    # Once Monday's session has completed (close + buffer) the same candle is accepted.
    service2, _ = make_service(settings, factory, provider, now=utc(2024, 3, 11, 20, 30))
    service2.ingest_symbol("US", "AAPL", force=True)
    with factory() as db:
        assert db.scalar(select(func.max(PriceBar.date))) == monday


def test_new_split_triggers_full_refetch(settings, factory, daily) -> None:  # type: ignore[no-untyped-def]
    bars = us_bars(settings, daily)
    provider = FakeProvider(bars={"AAPL": bars[:-1]})
    friday_before_close = utc(2024, 3, 8, 12, 0)  # last completed: Thu 7 Mar
    service, clock = make_service(settings, factory, provider, now=friday_before_close)
    service.ingest_symbol("US", "AAPL")
    provider.calls.clear()

    # A 2-for-1 split lands on Friday: the provider now reports all history halved.
    halved = [
        replace(
            b,
            open=b.open / 2,
            high=b.high / 2,
            low=b.low / 2,
            close=b.close / 2,
            adj_close=b.adj_close / 2,
        )
        for b in bars
    ]
    provider.bars["AAPL"] = halved
    provider.actions["AAPL"] = [RawAction(LAST, "split", 2.0)]
    clock.now = SATURDAY
    result = service.ingest_symbol("US", "AAPL")

    assert result.full_refetch
    assert [c[1] for c in provider.calls] == [D(2024, 3, 7) - dt.timedelta(days=7), bars[0].date]
    with factory() as db:
        first = db.scalars(
            select(PriceBar).where(PriceBar.symbol == "AAPL").order_by(PriceBar.date)
        ).first()
        assert first is not None and first.close == pytest.approx(
            bars[0].close / 2
        )  # old rows rewritten
        action = db.scalars(select(CorporateAction).where(CorporateAction.symbol == "AAPL")).one()
        assert (action.date, action.action_type, action.value) == (LAST, "split", 2.0)
    assert count(factory, "AAPL") == len(bars)
    assert issues(factory, "AAPL") == []  # the split is recorded, so nothing looks suspicious


def test_new_dividend_also_triggers_full_refetch(settings, factory, daily) -> None:  # type: ignore[no-untyped-def]
    bars = us_bars(settings, daily)
    provider = FakeProvider(bars={"AAPL": bars[:-1]})
    service, clock = make_service(settings, factory, provider, now=utc(2024, 3, 8, 12, 0))
    service.ingest_symbol("US", "AAPL")
    provider.bars["AAPL"] = bars
    provider.actions["AAPL"] = [RawAction(LAST, "dividend", 0.24)]
    clock.now = SATURDAY
    assert service.ingest_symbol("US", "AAPL").full_refetch


def test_gap_and_suspicious_move_are_recorded(settings, factory, daily) -> None:  # type: ignore[no-untyped-def]
    bars = us_bars(settings, daily)
    gap_day = bars[-10].date
    spiked = replace(
        bars[-3],
        close=bars[-4].close * 1.6,
        adj_close=bars[-4].close * 1.6,
        high=bars[-4].close * 1.7,
    )
    provider = FakeProvider(
        bars={"AAPL": [b for b in [*bars[:-3], spiked, *bars[-2:]] if b.date != gap_day]}
    )
    service, _ = make_service(settings, factory, provider)
    service.ingest_symbol("US", "AAPL")
    found = issues(factory, "AAPL")
    assert (quality.MISSING_SESSION, gap_day) in found
    assert (quality.SUSPICIOUS_MOVE, spiked.date) in found
    assert (quality.SUSPICIOUS_MOVE, bars[-2].date) in found  # and the move back down


def test_zero_volume_flagged_for_stock_not_index(settings, factory, daily) -> None:  # type: ignore[no-untyped-def]
    base = us_bars(settings, daily)
    bars = [*base[:-2], *(replace(b, volume=0.0) for b in base[-2:])]
    zero_days = [b.date for b in bars if b.volume == 0]
    provider = FakeProvider(bars={"AAPL": bars, "^GSPC": bars})
    service, _ = make_service(settings, factory, provider)
    service.ingest_symbol("US", "AAPL")
    service.ingest_symbol("US", "^GSPC")
    assert len(zero_days) >= 1
    assert issues(factory, "AAPL") == sorted(((quality.ZERO_VOLUME, d) for d in zero_days), key=str)
    assert issues(factory, "^GSPC") == []


def test_failures_are_recorded_and_do_not_stop_the_run(settings, factory, daily) -> None:  # type: ignore[no-untyped-def]
    provider = FakeProvider(
        bars={"MSFT": us_bars(settings, daily)},
        failing={
            "AAPL": SymbolNotFoundError("AAPL: no data from yfinance"),
            "NVDA": ProviderError("NVDA: timed out"),
        },
    )
    service, _ = make_service(settings, factory, provider)
    results = {r.symbol: r for r in service.ingest_all(symbols=["AAPL", "MSFT", "NVDA"])}
    assert results["AAPL"].outcome == "failed" and "no data" in (results["AAPL"].error or "")
    assert results["NVDA"].outcome == "failed"
    assert results["MSFT"].outcome == "fetched"
    assert count(factory, "AAPL") == 0  # nothing invented for a failed symbol
    with factory() as db:
        status = db.scalars(select(FetchStatus).where(FetchStatus.symbol == "AAPL")).one()
        assert status.last_outcome == "failed" and status.last_success_at is None
        assert status.last_error == "AAPL: no data from yfinance"


def test_rejected_rows_are_not_stored(settings, factory, daily) -> None:  # type: ignore[no-untyped-def]
    bars = us_bars(settings, daily)
    bad = replace(bars[-1], high=bars[-1].low - 1)
    provider = FakeProvider(bars={"AAPL": [*bars[:-1], bad]})
    service, _ = make_service(settings, factory, provider)
    service.ingest_symbol("US", "AAPL")
    assert count(factory, "AAPL") == len(bars) - 1
    found = issues(factory, "AAPL")
    assert (quality.REJECTED_ROW, LAST) in found and (quality.MISSING_SESSION, LAST) in found
