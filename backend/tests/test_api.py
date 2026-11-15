"""API routes end to end, with a temporary database and the in-memory provider."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import deps, routes
from app.config import Settings
from app.core import indicators as ind
from app.db import Base, get_db, make_engine
from app.main import app
from app.services.analysis import AnalysisService
from app.services.ingestion import IngestionService
from tests.helpers import FakeProvider, bars_on_sessions, calendar_for, utc

SATURDAY = utc(2024, 3, 9, 12, 0)
LAST = dt.date(2024, 3, 8)


class Api:
    def __init__(
        self, client: TestClient, provider: FakeProvider, clock: list[dt.datetime]
    ) -> None:
        self.client = client
        self.provider = provider
        self._clock = clock

    def set_now(self, now: dt.datetime) -> None:
        self._clock[0] = now


@pytest.fixture
def api(
    tmp_path: Path,
    settings: Settings,
    daily: pd.DataFrame,
    benchmark: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Api]:
    engine = make_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    provider = FakeProvider()
    start = LAST - dt.timedelta(days=366 * settings.provider.history_years)
    for market, symbol in settings.all_symbols():
        sessions = calendar_for(settings, market).sessions_between(start, LAST)
        source = benchmark if settings.is_benchmark(symbol) else daily
        provider.bars[symbol] = bars_on_sessions(source, sessions)

    clock = [SATURDAY]
    monkeypatch.setattr(routes, "utc_now", lambda: clock[0])

    def override_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[deps.get_settings_dep] = lambda: settings
    app.dependency_overrides[deps.get_analysis] = lambda: AnalysisService(settings, source="fake")
    app.dependency_overrides[deps.get_ingestion] = lambda: IngestionService(
        settings, provider, factory, now=lambda: clock[0]
    )
    yield Api(TestClient(app), provider, clock)
    app.dependency_overrides.clear()


def test_health_reports_no_scheduler(api: Api) -> None:
    body = api.client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["scheduler"]["active"] is False
    assert body["scheduler"]["last_successful_run_utc"] is None


def test_empty_database_shows_unavailable_not_numbers(api: Api) -> None:
    body = api.client.get("/api/watchlists").json()
    row = body["markets"][0]["rows"][0]
    assert row["freshness"] == "missing" and row["values"] == {} and row["candle_date"] is None
    assert "no data stored" in row["unavailable_reason"]

    detail = api.client.get("/api/symbols/AAPL/indicators").json()
    assert detail["snapshot"] == {} and detail["series"] == {} and detail["profile"] is None
    assert api.client.get("/api/symbols/AAPL/prices").json()["bars"] == []

    status = api.client.get("/api/sources/status").json()
    us = next(m for m in status["markets"] if m["code"] == "US")
    assert us["freshness_counts"] == {"fresh": 0, "stale": 0, "missing": 10, "unknown": 0}
    assert status["provider"]["last_success_utc"] is None


def test_ingest_then_every_page_endpoint_has_data(
    api: Api, settings: Settings, daily: pd.DataFrame
) -> None:
    result = api.client.post("/api/ingest", json={}).json()
    assert (result["fetched"], result["failed"]) == (20, 0)
    assert {r["symbol"] for r in result["results"]} == {s for _, s in settings.all_symbols()}

    status = api.client.get("/api/sources/status").json()
    counts = {m["code"]: m["freshness_counts"] for m in status["markets"]}
    assert counts["US"]["fresh"] == 10 and counts["IN"]["fresh"] == 10
    assert status["provider"]["data_kind"] == "delayed / end-of-day"
    assert status["provider"]["last_success_utc"] == "2024-03-09T12:00:00Z"
    assert status["scheduler"]["active"] is False
    us_clock = next(m for m in status["markets"] if m["code"] == "US")["clock"]
    assert us_clock["last_completed_session"] == "2024-03-08" and us_clock["is_open"] is False
    assert us_clock["now_local"] == "2024-03-09T07:00:00-05:00"

    lists = {m["code"]: m for m in api.client.get("/api/watchlists").json()["markets"]}
    aapl = next(r for r in lists["US"]["rows"] if r["symbol"] == "AAPL")
    assert aapl["currency"] == "USD" and aapl["freshness"] == "fresh"
    assert aapl["candle_date"] == "2024-03-08"
    assert aapl["as_of_local"] == "2024-03-08T16:00:00-05:00"
    assert aapl["fetched_at_utc"] == "2024-03-09T12:00:00Z" and aapl["source"] == "fake"
    assert aapl["values"]["last_close"] == pytest.approx(daily["close"].iloc[-1])
    assert aapl["relative_strength_benchmark"] == "^GSPC"
    assert aapl["values"]["relative_strength"] is not None

    tcs = next(r for r in lists["IN"]["rows"] if r["symbol"] == "TCS.NS")
    assert tcs["currency"] == "INR" and tcs["timezone"] == "Asia/Kolkata"
    assert tcs["as_of_local"] == "2024-03-07T15:30:00+05:30"  # 8 Mar 2024 is a holiday in India
    assert tcs["relative_strength_benchmark"] == "^NSEI"

    gspc = next(r for r in lists["US"]["rows"] if r["symbol"] == "^GSPC")
    assert gspc["values"]["relative_strength"] is None
    assert "benchmark itself" in gspc["unavailable"]["relative_strength"]


def test_indicator_endpoint_matches_core_functions(
    api: Api, settings: Settings, daily: pd.DataFrame
) -> None:
    api.client.post("/api/ingest", json={"symbols": ["AAPL", "^GSPC"]})
    body = api.client.get("/api/symbols/AAPL/indicators", params={"sessions": 120}).json()

    stored = daily.tail(body["sessions_stored"])["close"].reset_index(drop=True)
    cfg = settings.indicators
    assert body["snapshot"]["rsi"] == pytest.approx(ind.rsi(stored, cfg.rsi_period).iloc[-1])
    assert body["snapshot"]["sma_200"] == pytest.approx(ind.sma(stored, 200).iloc[-1])
    assert body["snapshot"]["pct_vs_sma_50"] == pytest.approx(
        (stored.iloc[-1] / ind.sma(stored, 50).iloc[-1] - 1) * 100
    )
    assert body["snapshot"]["return_5"] == pytest.approx(stored.iloc[-1] / stored.iloc[-6] - 1)
    assert body["candle_date"] == "2024-03-08" and body["source"] == "fake"
    assert body["fetched_at_utc"] == "2024-03-09T12:00:00Z"
    assert len(body["dates"]) == 120 and body["dates"][-1] == "2024-03-08"
    assert all(len(values) == 120 for values in body["series"].values())
    assert body["profile"]["name"] == "Synthetic AAPL"
    assert body["unavailable"] == {}
    for level in [*body["support"], *body["resistance"]]:
        assert level["confirmed_date"] > level["pivot_date"]  # confirmed by later candles
    assert all(lv["price"] < body["snapshot"]["last_adj_close"] for lv in body["support"])
    assert all(lv["price"] > body["snapshot"]["last_adj_close"] for lv in body["resistance"])


def test_short_history_reports_insufficient_data(api: Api) -> None:
    api.provider.bars["AAPL"] = api.provider.bars["AAPL"][-30:]
    api.client.post("/api/ingest", json={"symbols": ["AAPL"]})
    body = api.client.get("/api/symbols/AAPL/indicators").json()
    assert body["snapshot"]["sma_20"] is not None
    assert body["snapshot"]["sma_200"] is None and body["snapshot"]["pct_vs_sma_200"] is None
    assert "insufficient data" in body["unavailable"]["sma_200"]
    assert "no stored data for ^GSPC" in body["unavailable"]["relative_strength"]


def test_prices_endpoint(api: Api, daily: pd.DataFrame) -> None:
    api.client.post("/api/ingest", json={"symbols": ["AAPL"]})
    body = api.client.get("/api/symbols/AAPL/prices", params={"sessions": 5}).json()
    assert [b["date"] for b in body["bars"]][-1] == "2024-03-08" and len(body["bars"]) == 5
    last = body["bars"][-1]
    assert last["close"] == pytest.approx(daily["close"].iloc[-1])
    assert last["fetched_at_utc"] == "2024-03-09T12:00:00Z"
    assert body["currency"] == "USD" and body["freshness"] == "fresh"


def test_data_goes_stale_after_the_next_completed_session(api: Api) -> None:
    api.client.post("/api/ingest", json={"symbols": ["AAPL"]})
    api.set_now(utc(2024, 3, 11, 15, 0))  # Monday, session in progress: still fresh
    assert api.client.get("/api/symbols/AAPL/prices").json()["freshness"] == "fresh"
    api.set_now(utc(2024, 3, 11, 20, 30))  # Monday's session completed
    assert api.client.get("/api/symbols/AAPL/prices").json()["freshness"] == "stale"
    status = api.client.get("/api/sources/status").json()
    assert next(s for s in status["symbols"] if s["symbol"] == "AAPL")["freshness"] == "stale"


def test_failed_symbol_is_listed_with_its_reason(api: Api) -> None:
    from app.providers.base import SymbolNotFoundError

    api.provider.failing["ITC.NS"] = SymbolNotFoundError("ITC.NS: no data from provider")
    result = api.client.post("/api/ingest", json={}).json()
    assert result["failed"] == 1
    status = api.client.get("/api/sources/status").json()
    itc = next(s for s in status["symbols"] if s["symbol"] == "ITC.NS")
    assert itc["freshness"] == "missing" and itc["last_error"] == "ITC.NS: no data from provider"
    assert status["provider"]["symbols_failing"] == ["ITC.NS"]


def test_caret_symbols_and_unknown_symbols(api: Api) -> None:
    api.client.post("/api/ingest", json={"symbols": ["^NSEI"]})
    assert api.client.get("/api/symbols/%5ENSEI/prices").json()["currency"] == "INR"
    assert api.client.get("/api/symbols/NOPE/prices").status_code == 404
    assert api.client.get("/api/symbols/NOPE/indicators").status_code == 404
    assert api.client.post("/api/ingest", json={"symbols": ["NOPE"]}).status_code == 404
