from __future__ import annotations

from app.config import load_settings
from tests.conftest import REPO_CONFIG


def test_repo_config_loads_and_has_twenty_stocks_per_market() -> None:
    settings = load_settings(REPO_CONFIG)
    for code in ("US", "IN"):
        market = settings.markets[code]
        assert len(market.symbols) == 20 and len(set(market.symbols)) == 20
        assert market.relative_strength_benchmark in market.benchmarks
        assert market.hedge_instrument in market.every_symbol()
    assert settings.market_of("XLK") == "US" and settings.market_of("NOPE") is None
    assert all(s.endswith(".NS") for s in settings.markets["IN"].symbols)
