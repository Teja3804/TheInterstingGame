"""Position sizing (CONTEXT.md section 9). Pure arithmetic, no I/O.

    Risk Budget = Portfolio Equity x Risk Percentage
    Shares      = floor(Risk Budget / |Entry - Stop|)

then capped by cash, the per-stock limit, the per-sector limit, the total open-risk limit
and the lot size. The result names the constraint that was binding.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SizingInput:
    equity: float
    cash: float
    entry: float
    stop: float
    risk_per_trade_pct: float
    max_stock_pct: float
    max_sector_pct: float
    max_open_risk_pct: float
    sector_exposure: float = 0.0  # value already held in this stock's sector
    open_risk: float = 0.0  # money at risk in trades already open
    lot_size: int = 1


@dataclass(frozen=True)
class SizingResult:
    shares: int
    binding_constraint: str
    risk_budget: float
    risk_per_share: float
    risk_amount: float  # shares x risk per share
    position_value: float  # shares x entry
    limits: dict[str, int]  # shares allowed by each constraint


def position_size(inputs: SizingInput) -> SizingResult:
    risk_per_share = abs(inputs.entry - inputs.stop)
    if inputs.entry <= 0 or risk_per_share <= 0 or inputs.equity <= 0 or inputs.lot_size < 1:
        raise ValueError("entry, equity and lot size must be positive and stop must differ")

    def whole(amount: float, per_share: float) -> int:
        return max(0, math.floor(amount / per_share + 1e-9))

    risk_budget = inputs.equity * inputs.risk_per_trade_pct / 100.0
    limits = {
        "risk per trade": whole(risk_budget, risk_per_share),
        "available cash": whole(inputs.cash, inputs.entry),
        "max allocation per stock": whole(
            inputs.equity * inputs.max_stock_pct / 100.0, inputs.entry
        ),
        "max allocation per sector": whole(
            inputs.equity * inputs.max_sector_pct / 100.0 - inputs.sector_exposure, inputs.entry
        ),
        "total open risk": whole(
            inputs.equity * inputs.max_open_risk_pct / 100.0 - inputs.open_risk, risk_per_share
        ),
    }
    binding = min(limits, key=lambda name: limits[name])
    shares = limits[binding]
    lots = shares // inputs.lot_size * inputs.lot_size
    if lots < shares:
        shares, binding = lots, "lot size"
    return SizingResult(
        shares=shares,
        binding_constraint=binding,
        risk_budget=risk_budget,
        risk_per_share=risk_per_share,
        risk_amount=shares * risk_per_share,
        position_value=shares * inputs.entry,
        limits=limits,
    )
