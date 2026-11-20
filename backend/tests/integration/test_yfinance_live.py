"""Live-network checks against Yahoo Finance. Skipped by default.

pytest -m integration
"""

from __future__ import annotations

import datetime as dt

import pytest

from app.config import Settings
from app.providers.yfinance_provider import YFinanceProvider

pytestmark = pytest.mark.integration


def test_every_configured_symbol_resolves(settings: Settings) -> None:
    provider = YFinanceProvider(settings.provider)
    end = dt.date.today()
    start = end - dt.timedelta(days=20)
    failures: dict[str, str] = {}
    for _, symbol in settings.all_symbols():
        try:
            history = provider.fetch_daily_history(symbol, start, end)
            assert history.bars, "no rows"
        except Exception as exc:  # collect every failure before reporting
            failures[symbol] = str(exc)
    assert not failures, f"symbols that did not resolve: {failures}"


def test_profile_has_currency(settings: Settings) -> None:
    provider = YFinanceProvider(settings.provider)
    assert provider.fetch_profile("AAPL").currency == "USD"
    assert provider.fetch_profile("RELIANCE.NS").currency == "INR"


@pytest.mark.parametrize(("symbol", "currency"), [("AAPL", "USD"), ("RELIANCE.NS", "INR")])
def test_quote_has_price_time_and_currency(settings: Settings, symbol: str, currency: str) -> None:
    quote = YFinanceProvider(settings.provider).fetch_quote(symbol)
    assert quote.price > 0 and quote.currency == currency
    assert quote.market_time <= dt.datetime.now(dt.UTC) + dt.timedelta(minutes=5)
    assert quote.daily_closes, "no recent daily closes"
