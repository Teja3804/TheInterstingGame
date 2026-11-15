"""Statistics on simulated trades (CONTEXT.md section 14) and resampling estimates. Pure.

Everything here describes BACKTEST results: what the rules would have done on past data.
None of it predicts the future.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.core.backtest import Trade


def wilson_interval(wins: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson score interval for a proportion. None when there are no trades."""
    if total == 0:
        return None
    p = wins / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def equity_curve(r_multiples: Sequence[float], risk_pct: float) -> list[float]:
    """Equity (start = 1.0) risking `risk_pct` of current equity per trade, in order."""
    equity, curve = 1.0, [1.0]
    for r in r_multiples:
        equity *= 1.0 + risk_pct / 100.0 * r
        curve.append(equity)
    return curve


def max_drawdown_pct(curve: Sequence[float]) -> float:
    peak, worst = -math.inf, 0.0
    for value in curve:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1.0)
    return worst * 100.0


def longest_losing_streak(r_multiples: Iterable[float]) -> int:
    longest = current = 0
    for r in r_multiples:
        current = current + 1 if r <= 0 else 0
        longest = max(longest, current)
    return longest


@dataclass(frozen=True)
class Summary:
    trades: int
    wins: int
    win_rate: float | None
    win_rate_low: float | None
    win_rate_high: float | None
    avg_win_r: float | None
    avg_loss_r: float | None
    expectancy_r: float | None
    profit_factor: float | None
    total_r: float
    total_return_pct: float  # compounded, risking risk_pct per trade
    max_drawdown_pct: float
    avg_holding_sessions: float | None
    avg_cost_pct: float | None
    worst_r: float | None
    best_r: float | None
    longest_losing_streak: int
    gap_stops: int
    worst_gap_r: float | None
    exit_reasons: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def summarise(trades: Sequence[Trade], risk_pct: float) -> Summary:
    """Closed trades only, ordered by exit date for the equity curve."""
    closed = sorted((t for t in trades if t.closed), key=lambda t: (str(t.exit_date), t.symbol))
    rs = [float(t.r_multiple) for t in closed if t.r_multiple is not None]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    interval = wilson_interval(len(wins), len(rs))
    curve = equity_curve(rs, risk_pct)
    gaps = [
        float(t.r_multiple) for t in closed if t.reason == "stop (gap)" and t.r_multiple is not None
    ]
    reasons: dict[str, int] = {}
    for trade in closed:
        reasons[trade.reason] = reasons.get(trade.reason, 0) + 1
    gross_loss = -sum(losses)
    return Summary(
        trades=len(rs),
        wins=len(wins),
        win_rate=len(wins) / len(rs) if rs else None,
        win_rate_low=interval[0] if interval else None,
        win_rate_high=interval[1] if interval else None,
        avg_win_r=float(np.mean(wins)) if wins else None,
        avg_loss_r=float(np.mean(losses)) if losses else None,
        expectancy_r=float(np.mean(rs)) if rs else None,
        profit_factor=sum(wins) / gross_loss if gross_loss > 0 else None,
        total_r=float(sum(rs)),
        total_return_pct=(curve[-1] - 1.0) * 100.0,
        max_drawdown_pct=max_drawdown_pct(curve),
        avg_holding_sessions=float(np.mean([t.holding_sessions for t in closed]))
        if closed
        else None,
        avg_cost_pct=float(np.mean([t.cost_pct for t in closed if t.cost_pct is not None]))
        if closed
        else None,
        worst_r=min(rs) if rs else None,
        best_r=max(rs) if rs else None,
        longest_losing_streak=longest_losing_streak(rs),
        gap_stops=len(gaps),
        worst_gap_r=min(gaps) if gaps else None,
        exit_reasons=reasons,
    )


@dataclass(frozen=True)
class Bootstrap:
    sample_trades: int
    horizon_trades: int
    paths: int
    prob_profit: float
    prob_drawdown: float
    drawdown_threshold_pct: float
    prob_losing_streak: float
    losing_streak: int
    return_p05_pct: float
    return_p50_pct: float
    return_p95_pct: float
    worst_drawdown_p95_pct: float

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def bootstrap(
    r_multiples: Sequence[float],
    horizon_trades: int,
    paths: int,
    risk_pct: float,
    drawdown_threshold_pct: float,
    losing_streak: int,
    min_trades: int,
    seed: int,
) -> Bootstrap | None:
    """Resample past trade results (with replacement) into `paths` sequences of
    `horizon_trades` trades. Returns None when there are fewer than `min_trades` results,
    because a probability from a tiny sample would not have statistical support.

    Assumes future trades look like a random draw from past ones and are independent of
    each other; real losses cluster, so treat the figures as optimistic about streaks.
    """
    if len(r_multiples) < min_trades:
        return None
    rng = np.random.default_rng(seed)
    sample = np.asarray(r_multiples, dtype=float)
    draws = rng.choice(sample, size=(paths, horizon_trades), replace=True)
    equity = np.cumprod(1.0 + risk_pct / 100.0 * draws, axis=1)
    with_start = np.concatenate([np.ones((paths, 1)), equity], axis=1)
    peaks = np.maximum.accumulate(with_start, axis=1)
    worst = (with_start / peaks - 1.0).min(axis=1) * 100.0
    final = (equity[:, -1] - 1.0) * 100.0

    losing = draws <= 0
    run = np.zeros(paths, dtype=int)
    longest = np.zeros(paths, dtype=int)
    for column in range(horizon_trades):
        run = np.where(losing[:, column], run + 1, 0)
        longest = np.maximum(longest, run)

    return Bootstrap(
        sample_trades=len(sample),
        horizon_trades=horizon_trades,
        paths=paths,
        prob_profit=float((final > 0).mean()),
        prob_drawdown=float((worst <= -drawdown_threshold_pct).mean()),
        drawdown_threshold_pct=drawdown_threshold_pct,
        prob_losing_streak=float((longest >= losing_streak).mean()),
        losing_streak=losing_streak,
        return_p05_pct=float(np.percentile(final, 5)),
        return_p50_pct=float(np.percentile(final, 50)),
        return_p95_pct=float(np.percentile(final, 95)),
        worst_drawdown_p95_pct=float(np.percentile(worst, 5)),
    )


def stressed_r(
    trades: Sequence[Trade], extra_cost_bps_per_side: float, stop_slippage_r: float
) -> list[float]:
    """Trade results re-stated under harsher assumptions: extra cost on both sides of every
    trade, and every stop exit filled `stop_slippage_r` R worse."""
    out: list[float] = []
    for trade in trades:
        if not trade.closed or trade.r_multiple is None:
            continue
        cost_in_r = 2 * extra_cost_bps_per_side / 10_000.0 * 100.0 / trade.planned_risk_pct
        slip = stop_slippage_r if trade.reason.startswith("stop") else 0.0
        out.append(trade.r_multiple - cost_in_r - slip)
    return out


def apply_position_cap(trades: Sequence[Trade], max_open: int) -> tuple[list[Trade], int]:
    """Portfolio view: take trades in entry-date order (ties by symbol) but never hold more
    than `max_open` at once. Returns (trades taken, signals skipped)."""
    taken: list[Trade] = []
    skipped = 0
    for trade in sorted(trades, key=lambda t: (str(t.entry_date), t.symbol)):
        entry = str(trade.entry_date)
        # A slot frees up on the exit day; the freed cash is usable from the next entry on.
        still_open = sum(1 for t in taken if t.exit_date is None or str(t.exit_date) > entry)
        if still_open < max_open:
            taken.append(trade)
        else:
            skipped += 1
    return taken, skipped
