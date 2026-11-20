"""Quote checks (pure) and the quote service against a temporary database.

Every price here is a synthetic number chosen for the test; none is market data.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.core import quotes as checks
from app.db import Base, make_engine
from app.models import LatestQuote, PriceBar
from app.providers.base import ProviderError, RawQuote
from app.services.quotes import QuoteService, quote_symbols
from tests.helpers import FakeProvider, utc

D = dt.date
# Fri 8 Mar 2024. US session 09:30-16:00 New York = 14:30-21:00 UTC.
US_OPEN_NOW = utc(2024, 3, 8, 18, 0)
US_AFTER_CLOSE = utc(2024, 3, 9, 12, 0)


def check(**overrides: object) -> checks.QuoteCheck:
    args: dict[str, object] = {
        "price": 100.0,
        "market_time_utc": utc(2024, 3, 8, 17, 45),
        "currency": "USD",
        "expected_currency": "USD",
        "reference_close": 98.0,
        "stored_close_same_session": None,
        "now_utc": US_OPEN_NOW,
        "max_future_seconds": 300.0,
        "suspicious_move_pct": 25.0,
        "close_match_tolerance_pct": 0.5,
    }
    args.update(overrides)
    return checks.check_quote(**args)  # type: ignore[arg-type]


# -- pure checks -----------------------------------------------------------------------


def test_previous_close_is_the_last_row_before_the_session() -> None:
    closes = [(D(2024, 3, 6), 10.0), (D(2024, 3, 7), 11.0), (D(2024, 3, 8), 12.0)]
    assert checks.previous_close(closes, D(2024, 3, 8)) == 11.0
    assert checks.previous_close(closes, D(2024, 3, 11)) == 12.0
    assert checks.previous_close(closes, D(2024, 3, 6)) is None
    assert checks.previous_close([(D(2024, 3, 7), float("nan"))], D(2024, 3, 8)) is None


def test_change_pct_hand_worked() -> None:
    assert checks.change_pct(110.0, 100.0) == pytest.approx(10.0)
    assert checks.change_pct(95.0, 100.0) == pytest.approx(-5.0)
    assert checks.change_pct(95.0, None) is None
    assert checks.change_pct(95.0, 0.0) is None


def test_clean_quote_is_usable_without_warnings() -> None:
    assert check() == checks.QuoteCheck(True, [])


@pytest.mark.parametrize("price", [0.0, -1.0, float("nan"), float("inf")])
def test_non_positive_or_non_finite_price_is_rejected(price: float) -> None:
    result = check(price=price)
    assert not result.usable and result.warnings[0].startswith(checks.NOT_POSITIVE)


def test_quote_time_in_the_future_is_rejected() -> None:
    result = check(market_time_utc=US_OPEN_NOW + dt.timedelta(minutes=10))
    assert not result.usable and result.warnings[0].startswith(checks.FUTURE_TIME)
    assert check(market_time_utc=US_OPEN_NOW + dt.timedelta(minutes=4)).usable


def test_warnings_keep_the_quote_but_say_why() -> None:
    result = check(currency="INR", reference_close=70.0, stored_close_same_session=99.0)
    assert result.usable
    kinds = [w.split(":")[0] for w in result.warnings]
    assert kinds == [checks.CURRENCY_MISMATCH, checks.LARGE_MOVE, checks.CLOSE_MISMATCH]
    # 100 / 99 - 1 = +1.01%, beyond the 0.5% tolerance
    assert "+1.01%" in result.warnings[2]


def test_close_within_tolerance_is_not_flagged() -> None:
    assert check(stored_close_same_session=100.4).warnings == []


# -- service ---------------------------------------------------------------------------


@pytest.fixture
def factory(tmp_path: Path) -> sessionmaker[Session]:
    engine = make_engine(f"sqlite:///{tmp_path / 'quotes.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def raw(symbol: str, price: float, when: dt.datetime, currency: str = "USD") -> RawQuote:
    closes = [(D(2024, 3, 6), price * 0.98), (D(2024, 3, 7), price * 0.99)]
    return RawQuote(symbol, price, when, currency, closes)


def service(
    settings: Settings, factory: sessionmaker[Session], provider: FakeProvider, now: dt.datetime
) -> QuoteService:
    return QuoteService(settings, provider, factory, now=lambda: now)


def fill_us(provider: FakeProvider, settings: Settings, when: dt.datetime) -> None:
    for i, symbol in enumerate(quote_symbols(settings.markets["US"])):
        provider.quotes[symbol] = raw(symbol, 100.0 + i, when)


def test_refresh_stores_every_us_stock_and_benchmark(
    settings: Settings, factory: sessionmaker[Session]
) -> None:
    provider = FakeProvider()
    fill_us(provider, settings, utc(2024, 3, 8, 17, 45))
    run = service(settings, factory, provider, US_OPEN_NOW).refresh(["US"])

    expected = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "^GSPC", "^NDX"]
    assert provider.quote_calls == expected
    assert (run.fetched, run.failed) == (7, 0)
    with factory() as db:
        row = db.query(LatestQuote).filter_by(symbol="AAPL").one()
        assert row.price == 100.0 and row.previous_close == pytest.approx(99.0)
        assert row.market_time == dt.datetime(2024, 3, 8, 17, 45)  # naive UTC
        assert row.fetched_at == dt.datetime(2024, 3, 8, 18, 0) and row.source == "fake"


def test_payload_labels_a_quote_during_the_session(
    settings: Settings, factory: sessionmaker[Session]
) -> None:
    provider = FakeProvider()
    fill_us(provider, settings, utc(2024, 3, 8, 17, 45))
    svc = service(settings, factory, provider, US_OPEN_NOW)
    svc.refresh(["US"])
    with factory() as db:
        body = svc.payload(db, US_OPEN_NOW)
    us = next(m for m in body["markets"] if m["code"] == "US")
    aapl = next(q for q in us["quotes"] if q["symbol"] == "AAPL")
    assert us["is_open"] is True
    assert aapl["kind"] == checks.DURING_SESSION
    assert aapl["market_time_utc"] == "2024-03-08T17:45:00Z"
    assert aapl["market_time_local"] == "2024-03-08T12:45:00-05:00"
    assert aapl["change_pct"] == pytest.approx(100.0 / 99.0 * 100 - 100)
    assert aapl["currency"] == "USD" and aapl["warnings"] == []

    india = next(m for m in body["markets"] if m["code"] == "IN")
    assert all(q["price"] is None for q in india["quotes"])
    assert india["quotes"][0]["unavailable_reason"] == "no quote fetched yet"


def test_payload_labels_a_quote_after_the_close(
    settings: Settings, factory: sessionmaker[Session]
) -> None:
    provider = FakeProvider()
    fill_us(provider, settings, utc(2024, 3, 8, 21, 0))
    svc = service(settings, factory, provider, US_AFTER_CLOSE)
    svc.refresh(["US"])
    with factory() as db:
        us = next(m for m in svc.payload(db, US_AFTER_CLOSE)["markets"] if m["code"] == "US")
    assert us["is_open"] is False
    assert us["quotes"][0]["kind"] == checks.AFTER_CLOSE


def test_failure_keeps_the_last_good_quote_and_records_the_error(
    settings: Settings, factory: sessionmaker[Session]
) -> None:
    provider = FakeProvider()
    fill_us(provider, settings, utc(2024, 3, 8, 17, 45))
    service(settings, factory, provider, US_OPEN_NOW).refresh(["US"])

    provider.quotes["AAPL"] = ProviderError("AAPL: rate limited")
    later = US_OPEN_NOW + dt.timedelta(minutes=15)
    svc = service(settings, factory, provider, later)
    run = svc.refresh(["US"])
    assert run.failed == 1 and run.errors == {"AAPL": "AAPL: rate limited"}
    with factory() as db:
        row = db.query(LatestQuote).filter_by(symbol="AAPL").one()
        assert row.price == 100.0 and row.market_time == dt.datetime(2024, 3, 8, 17, 45)
        assert row.last_error == "AAPL: rate limited"
        assert row.last_error_at == dt.datetime(2024, 3, 8, 18, 15)
        item = next(
            q for q in svc.payload(db, later)["markets"][0]["quotes"] if q["symbol"] == "AAPL"
        )
    assert item["price"] == 100.0 and item["last_error"] == "AAPL: rate limited"


def test_rejected_quote_is_not_stored(settings: Settings, factory: sessionmaker[Session]) -> None:
    provider = FakeProvider()
    fill_us(provider, settings, utc(2024, 3, 8, 17, 45))
    provider.quotes["AAPL"] = raw("AAPL", 0.0, utc(2024, 3, 8, 17, 45))
    run = service(settings, factory, provider, US_OPEN_NOW).refresh(["US"])
    assert "quote rejected" in run.errors["AAPL"]
    with factory() as db:
        row = db.query(LatestQuote).filter_by(symbol="AAPL").one()
        assert row.price is None and "price_not_positive" in (row.last_error or "")


def test_quote_after_close_is_checked_against_the_stored_candle(
    settings: Settings, factory: sessionmaker[Session]
) -> None:
    with factory() as db:
        db.add(
            PriceBar(
                symbol="AAPL", market="US", date=D(2024, 3, 8), open=1, high=1, low=1,
                close=95.0, adj_close=95.0, volume=1, source="fake",
                fetched_at=dt.datetime(2024, 3, 9, 12, 0),
            )
        )  # fmt: skip
        db.commit()
    provider = FakeProvider()
    fill_us(provider, settings, utc(2024, 3, 8, 21, 0))  # AAPL quote 100.0 vs stored 95.0
    run = service(settings, factory, provider, US_AFTER_CLOSE).refresh(["US"])
    assert run.warnings["AAPL"][0].startswith(checks.CLOSE_MISMATCH)
    assert "+5.26%" in run.warnings["AAPL"][0]
