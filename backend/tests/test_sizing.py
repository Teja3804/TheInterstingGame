"""Position-size maths, each expected number worked out by hand in the comments."""

from __future__ import annotations

import pytest

from app.core.sizing import SizingInput, position_size

BASE = dict(
    equity=100_000.0,
    cash=100_000.0,
    entry=50.0,
    stop=48.0,
    risk_per_trade_pct=0.5,
    max_stock_pct=10.0,
    max_sector_pct=25.0,
    max_open_risk_pct=2.0,
)


def size(**over: float) -> tuple[int, str]:
    result = position_size(SizingInput(**{**BASE, **over}))  # type: ignore[arg-type]
    return result.shares, result.binding_constraint


def test_risk_budget_formula() -> None:
    # budget = 100,000 x 0.5% = 500; risk per share = 2; 500 / 2 = 250 shares.
    # stock cap = 10,000 / 50 = 200 shares, which is lower, so use a wider cap here.
    result = position_size(SizingInput(**{**BASE, "max_stock_pct": 50.0, "max_sector_pct": 50.0}))
    assert result.risk_budget == 500.0 and result.risk_per_share == 2.0
    assert (result.shares, result.binding_constraint) == (250, "risk per trade")
    assert result.risk_amount == 500.0 and result.position_value == 12_500.0


def test_fractional_shares_round_down() -> None:
    # 500 / 3 = 166.67 -> 166 shares, never rounded up past the risk budget.
    assert size(stop=47.0, max_stock_pct=50.0, max_sector_pct=50.0) == (166, "risk per trade")


def test_stock_cap_binds() -> None:
    # 10% of 100,000 = 10,000; 10,000 / 50 = 200 shares < 250 from risk.
    assert size() == (200, "max allocation per stock")


def test_cash_binds() -> None:
    assert size(cash=4_000.0) == (80, "available cash")  # 4,000 / 50


def test_sector_cap_binds() -> None:
    # 25% of 100,000 = 25,000; 21,000 already held; 4,000 / 50 = 80 shares.
    assert size(sector_exposure=21_000.0) == (80, "max allocation per sector")
    assert size(sector_exposure=30_000.0) == (0, "max allocation per sector")


def test_open_risk_cap_binds() -> None:
    # 2% of 100,000 = 2,000; 1,800 already at risk; 200 / 2 = 100 shares.
    assert size(open_risk=1_800.0) == (100, "total open risk")
    assert size(open_risk=2_500.0) == (0, "total open risk")


def test_lot_size_rounds_down() -> None:
    assert size(lot_size=75) == (150, "lot size")  # 200 -> 150


def test_stop_above_entry_uses_absolute_distance() -> None:
    assert size(stop=52.0) == size(stop=48.0)


@pytest.mark.parametrize("bad", [{"stop": 50.0}, {"entry": 0.0}, {"equity": 0.0}])
def test_invalid_inputs_raise(bad: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        position_size(SizingInput(**{**BASE, **bad}))  # type: ignore[arg-type]
