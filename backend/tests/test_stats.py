from __future__ import annotations

import pytest

from app.core import stats
from app.core.backtest import Trade


def trade(r: float, reason: str = "target", risk_pct: float = 2.0, day: int = 1) -> Trade:
    return Trade(
        "T",
        f"2024-01-{day:02d}",
        f"2024-01-{day:02d}",
        100.0,
        98.0,
        f"2024-02-{day:02d}",
        100.0 + r * 2,
        reason,
        5,
        r,
        r * risk_pct,
        0.1,
        risk_pct,
    )


def test_wilson_interval_known_values() -> None:
    low, high = stats.wilson_interval(5, 10)  # type: ignore[misc]
    assert (low, high) == pytest.approx((0.2366, 0.7634), abs=1e-4)
    assert stats.wilson_interval(0, 0) is None
    low, high = stats.wilson_interval(10, 10)  # type: ignore[misc]
    assert high == pytest.approx(1.0) and 0.7 < low < 0.73


def test_equity_curve_drawdown_and_streak() -> None:
    curve = stats.equity_curve([1.0, -1.0, -1.0, 2.0], risk_pct=1.0)
    assert curve == pytest.approx([1, 1.01, 0.9999, 0.989901, 1.00969902])
    assert stats.max_drawdown_pct(curve) == pytest.approx((0.989901 / 1.01 - 1) * 100)
    assert stats.longest_losing_streak([1, -1, -1, 0, 2, -1]) == 3  # a zero result counts as a loss
    assert stats.max_drawdown_pct([1.0]) == 0.0


def test_summary_by_hand() -> None:
    trades = [
        trade(2.0, day=1),
        trade(-1.0, "stop", day=2),
        trade(-1.5, "stop (gap)", day=3),
        trade(1.0, "time", day=4),
    ]
    s = stats.summarise(trades, risk_pct=1.0)
    assert (s.trades, s.wins) == (4, 2) and s.win_rate == 0.5
    assert s.avg_win_r == pytest.approx(1.5) and s.avg_loss_r == pytest.approx(-1.25)
    assert s.expectancy_r == pytest.approx(0.125)  # (2 - 1 - 1.5 + 1) / 4
    assert s.profit_factor == pytest.approx(3 / 2.5)
    assert (s.gap_stops, s.worst_gap_r, s.worst_r, s.best_r) == (1, -1.5, -1.5, 2.0)
    assert s.exit_reasons == {"target": 1, "stop": 1, "stop (gap)": 1, "time": 1}
    assert s.longest_losing_streak == 2
    assert s.total_return_pct == pytest.approx((1.02 * 0.99 * 0.985 * 1.01 - 1) * 100)


def test_open_trades_are_left_out_and_empty_is_safe() -> None:
    still_open = Trade("T", "d", "d", 100.0, 98.0, None, None, "open", 3, None, None, None, 2.0)
    s = stats.summarise([still_open], risk_pct=1.0)
    assert s.trades == 0 and s.win_rate is None and s.expectancy_r is None
    assert s.profit_factor is None and s.max_drawdown_pct == 0.0


def test_bootstrap_refuses_small_samples() -> None:
    args = dict(
        horizon_trades=20,
        paths=500,
        risk_pct=0.5,
        drawdown_threshold_pct=5.0,
        losing_streak=5,
        min_trades=30,
        seed=1,
    )
    assert stats.bootstrap([1.0] * 29, **args) is None  # type: ignore[arg-type]
    assert stats.bootstrap([1.0] * 30, **args) is not None  # type: ignore[arg-type]


def test_bootstrap_extremes_and_determinism() -> None:
    args = dict(
        horizon_trades=20,
        paths=2000,
        risk_pct=1.0,
        drawdown_threshold_pct=5.0,
        losing_streak=5,
        min_trades=30,
        seed=7,
    )
    winners = stats.bootstrap([1.0] * 40, **args)  # type: ignore[arg-type]
    assert winners is not None
    assert (winners.prob_profit, winners.prob_drawdown, winners.prob_losing_streak) == (
        1.0,
        0.0,
        0.0,
    )
    assert winners.return_p50_pct == pytest.approx((1.01**20 - 1) * 100)

    losers = stats.bootstrap([-1.0] * 40, **args)  # type: ignore[arg-type]
    assert losers is not None
    assert (losers.prob_profit, losers.prob_drawdown, losers.prob_losing_streak) == (0.0, 1.0, 1.0)

    mixed = [1.5] * 20 + [-1.0] * 20
    first, second = stats.bootstrap(mixed, **args), stats.bootstrap(mixed, **args)  # type: ignore[arg-type]
    assert first == second  # same seed, same answer
    assert first is not None and 0.0 < first.prob_profit < 1.0
    assert first.return_p05_pct < first.return_p50_pct < first.return_p95_pct


def test_stress_restates_each_trade() -> None:
    trades = [trade(2.0), trade(-1.0, "stop"), trade(-1.5, "stop (gap)")]
    # 10 bps extra per side on a 2% planned risk = 2 x 0.10% / 2% = 0.1 R per trade
    assert stats.stressed_r(trades, 10.0, 0.5) == pytest.approx([1.9, -1.6, -2.1])
    assert stats.stressed_r(trades, 0.0, 0.0) == pytest.approx([2.0, -1.0, -1.5])


def test_position_cap_takes_trades_in_date_order() -> None:
    def spanning(symbol: str, start: int, end: int | None) -> Trade:
        exit_day = None if end is None else f"2024-01-{end:02d}"
        return Trade(
            symbol,
            "s",
            f"2024-01-{start:02d}",
            100.0,
            98.0,
            exit_day,
            101.0,
            "time",
            3,
            0.5 if end else None,
            1.0,
            0.1,
            2.0,
        )

    a, b, c, d = spanning("A", 1, 10), spanning("B", 2, 5), spanning("C", 3, 8), spanning("D", 5, 9)
    taken, skipped = stats.apply_position_cap([d, c, b, a], max_open=2)
    # A and B fill both slots; C (day 3) is skipped; B exits on day 5, so D (day 5) fits.
    assert [t.symbol for t in taken] == ["A", "B", "D"] and skipped == 1
    still_open = spanning("E", 1, None)
    taken, skipped = stats.apply_position_cap([still_open, b], max_open=1)
    assert [t.symbol for t in taken] == ["E"] and skipped == 1
