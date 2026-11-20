"""The three screens' API routes, end to end on synthetic candles."""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import deps, routes
from app.config import Settings
from app.db import Base, get_db, make_engine
from app.export import export, safe_name
from app.main import app
from app.services.analysis import AnalysisService
from app.services.ingestion import IngestionService
from app.services.quotes import QuoteService
from app.services.research import ResearchService
from tests.helpers import FakeProvider, bars_on_sessions, calendar_for, utc

SATURDAY = utc(2024, 3, 9, 12, 0)
LAST = dt.date(2024, 3, 8)


@pytest.fixture
def client(
    tmp_path: Path,
    settings: Settings,
    daily: pd.DataFrame,
    benchmark: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    engine = make_engine(f"sqlite:///{tmp_path / 'research.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    provider = FakeProvider()
    start = LAST - dt.timedelta(days=366 * settings.provider.history_years)
    for market, symbol in settings.all_symbols():
        sessions = calendar_for(settings, market).sessions_between(start, LAST)
        source = daily if symbol in settings.markets[market].symbols else benchmark
        provider.bars[symbol] = bars_on_sessions(source, sessions)
    provider.bars.pop("NVDA")  # one stock with no data at all
    IngestionService(settings, provider, factory, now=lambda: SATURDAY).ingest_all()

    analysis = AnalysisService(settings, source="fake")
    research = ResearchService(settings, analysis)
    monkeypatch.setattr(routes, "utc_now", lambda: SATURDAY)

    def override_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[deps.get_settings_dep] = lambda: settings
    app.dependency_overrides[deps.get_analysis] = lambda: analysis
    app.dependency_overrides[deps.get_research] = lambda: research
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_stocks_list_has_scores_suggestions_and_provenance(client: TestClient) -> None:
    body = client.get("/api/stocks").json()
    us = next(m for m in body["markets"] if m["code"] == "US")
    assert us["regime"]["label"] in {"Bullish", "Neutral", "Bearish", "Uncertain"}
    assert us["regime"]["as_of"] == "2024-03-08" and us["regime"]["evidence"]
    rows = {r["symbol"]: r for r in us["rows"]}
    assert set(rows) == {"AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"}  # watchlist only, no references
    aapl = rows["AAPL"]
    assert 0 <= aapl["score"] <= 100 and aapl["freshness"] == "fresh"
    assert aapl["candle_date"] == "2024-03-08" and aapl["currency"] == "USD"
    assert aapl["suggestion"]["action"] in {"Buy candidate", "Watch", "No trade", "Rejected"}
    assert aapl["suggestion"]["reasons"] and len(aapl["spark"]) == 60
    assert rows["NVDA"]["suggestion"]["action"] == "Unavailable" and rows["NVDA"]["score"] is None
    assert "not a probability" in body["note"]


def test_insight_explains_the_score_and_plan(client: TestClient, settings: Settings) -> None:
    body = client.get("/api/symbols/AAPL/insight").json()
    assert body["available"] and len(body["components"]) == 6
    weights = {c["key"]: c["weight"] for c in body["components"]}
    assert weights == settings.scoring.weights
    used = [c for c in body["components"] if c["score"] is not None]
    assert body["weight_used"] == sum(c["weight"] for c in used)
    assert body["score"] == pytest.approx(
        sum(c["weight"] * c["score"] for c in used) / body["weight_used"]
    )
    for component in body["components"]:
        assert component["formula"] and component["inputs"]
        assert (component["score"] is None) == (component["unavailable_reason"] is not None)

    plan = body["plan"]
    assert plan["stop"] < plan["entry_reference"] < plan["target"]
    assert plan["entry_reference"] - plan["stop"] == pytest.approx(plan["risk_per_share"])
    assert plan["target"] - plan["entry_reference"] == pytest.approx(2 * plan["risk_per_share"])
    sizing = plan["sizing"]
    assert sizing["risk_amount"] <= sizing["risk_budget"] + 1e-9
    assert sizing["shares"] == min(sizing["limits"].values())
    assert [s["name"] for s in plan["scenarios"]] == ["Bullish", "Base", "Bearish"]

    assert body["if_held"]["action"] in {"Hold", "Exit", "Hold, consider hedging or reducing"}
    assert len(body["if_held"]["options"]) == 4
    assert body["hedge"]["instrument"] == "SPY" and body["hedge"]["limitations"]
    assert any("Earnings" in note for note in body["not_checked"])
    assert body["backtest_history"]["label"] == "BACKTEST"


def test_insight_edge_cases(client: TestClient) -> None:
    assert client.get("/api/symbols/NVDA/insight").json() == {
        "available": False,
        "reason": "no data stored; run a refresh",
    }
    assert client.get("/api/symbols/SPY/insight").status_code == 404  # reference symbol
    assert client.get("/api/symbols/NOPE/insight").status_code == 404


def test_risk_analysis_is_labelled_and_consistent(client: TestClient, settings: Settings) -> None:
    body = client.get("/api/risk").json()
    assert body["label"] == "BACKTEST" and body["strategy"]["name"].startswith("Scoring model")
    assert any("Survivorship" in w for w in body["warnings"])
    for market in body["markets"]:
        summary = market["summary"]
        assert summary["trades"] == sum(summary["exit_reasons"].values())
        for split in ("by_volatility", "by_regime", "by_period"):
            assert sum(b["trades"] for b in market[split]) == summary["trades"]
        assert [s["name"] for s in market["stress"]][0] == "As tested"
        if summary["trades"]:
            tested, both = market["stress"][0], market["stress"][-1]
            assert tested["expectancy_r"] == pytest.approx(summary["expectancy_r"])
            assert both["expectancy_r"] < tested["expectancy_r"]  # harsher is never better
        probability = market["probability"]
        minimum = settings.risk.analysis.min_trades_for_probability
        assert probability["available"] == (summary["trades"] >= minimum)
        if not probability["available"]:
            assert "statistical support" in probability["reason"]
        else:
            assert 0 <= probability["prob_profit"] <= 1
        limits = market["loss_limits"]
        assert limits["max_simultaneous_trades_at_full_risk"] == 4
        assert limits["all_open_trades_gap_pct_of_equity"] == pytest.approx(-6.0)
        assert market["portfolio"]["trades_taken"] <= summary["trades"]
        assert market["findings"]


def test_strategy_comparison(client: TestClient) -> None:
    body = client.get("/api/strategies").json()
    assert body["label"] == "BACKTEST"
    for market in body["markets"]:
        rows = market["strategies"]
        assert len(rows) == 6 and sum(r["is_current"] for r in rows) == 1
        current = next(r for r in rows if r["is_current"])
        assert current["expectancy_vs_current_r"] is None
        for row in rows:
            assert row["rule"] and "summary" in row and "portfolio" in row
            assert set(row["signals_now"]) <= {s for s in market_symbols(body, market["code"])}
        assert market["benchmark"]["buy_and_hold_return_pct"] is not None


def market_symbols(body: dict, code: str) -> set[str]:  # type: ignore[type-arg]
    known = {
        "US": {"AAPL", "MSFT", "AMZN", "GOOGL"},
        "IN": {"RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "ITC.NS"},
    }
    return known[code]


def test_risk_matches_strategy_table_for_the_current_strategy(client: TestClient) -> None:
    risk = client.get("/api/risk").json()
    table = client.get("/api/strategies").json()
    for r_market, s_market in zip(risk["markets"], table["markets"], strict=True):
        current = next(r for r in s_market["strategies"] if r["is_current"])
        assert current["summary"] == r_market["summary"]


def test_export_writes_one_file_per_stock(
    client: TestClient, tmp_path: Path, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import export as module

    overrides = app.dependency_overrides
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(module, "get_analysis", overrides[deps.get_analysis])
    monkeypatch.setattr(module, "get_research", overrides[deps.get_research])
    monkeypatch.setattr(module, "init_db", lambda: None)
    monkeypatch.setattr(module, "utc_now", lambda: SATURDAY)

    sessions = list(overrides[get_db]())
    factory = lambda: _Ctx(sessions[0])  # noqa: E731
    monkeypatch.setattr(module, "get_session_factory", lambda: factory)
    quotes = QuoteService(settings, FakeProvider(), factory)  # type: ignore[arg-type]
    monkeypatch.setattr(module, "get_quotes", lambda: quotes)
    count = export(tmp_path / "snap", 60, scheduled=True)
    assert count == 5 + 11
    assert (tmp_path / "snap" / "symbols" / "AAPL.json").exists()
    status = json.loads((tmp_path / "snap" / "status.json").read_text())
    assert status["snapshot"]["scheduled"] is True
    assert status["snapshot"]["update_every_minutes"] == settings.site.update_every_minutes
    body = json.loads((tmp_path / "snap" / "quotes.json").read_text())
    assert body["markets"][0]["quotes"][0]["unavailable_reason"] == "no quote fetched yet"
    assert safe_name("^GSPC") == "_GSPC" and safe_name("M&M.NS") == "M_M.NS"


class _Ctx:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __enter__(self) -> Session:
        return self.session

    def __exit__(self, *args: object) -> None:
        return None
