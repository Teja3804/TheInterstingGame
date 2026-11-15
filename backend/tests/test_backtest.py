"""Trade simulator, on tiny hand-built price paths so every fill can be checked by eye.
ATR is 1 and the stop multiple 2, so the planned risk is 2 per share throughout."""

from __future__ import annotations

import pandas as pd
import pytest

from app.core.backtest import Execution, simulate

FREE = Execution(
    stop_atr_multiple=2.0,
    target_r_multiple=2.0,
    max_holding_sessions=10,
    slippage_bps=0.0,
    cost_bps_per_side=0.0,
)


def frame(rows: list[tuple[float, float, float, float]], atr: float = 1.0) -> pd.DataFrame:
    out = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    out["atr"] = atr
    out.index = pd.date_range("2024-01-01", periods=len(rows)).date
    return out


def signals(n: int, *on: int) -> pd.Series:
    return pd.Series([i in on for i in range(n)])


def run(rows, entries=(0,), exits=None, execution=FREE, atr=1.0):  # type: ignore[no-untyped-def]
    f = frame(rows, atr)
    e = pd.Series([i in entries for i in range(len(rows))], index=f.index)
    x = None if exits is None else pd.Series([i in exits for i in range(len(rows))], index=f.index)
    return simulate("T", f, e, x, execution)


def test_fills_at_next_open_and_hits_target() -> None:
    # signal on day 0, entry at day 1 open 10; stop 8, target 14; day 2 high 14.5.
    trades = run([(9, 9, 9, 9), (10, 10.5, 9.5, 10), (10, 14.5, 10, 14), (14, 14, 14, 14)])
    (t,) = trades
    assert (str(t.entry_date), t.entry_price, t.stop_price) == ("2024-01-02", 10.0, 8.0)
    assert (t.reason, t.exit_price, str(t.exit_date)) == ("target", 14.0, "2024-01-03")
    assert t.r_multiple == pytest.approx(2.0) and t.return_pct == pytest.approx(40.0)
    assert t.holding_sessions == 2 and t.planned_risk_pct == pytest.approx(20.0)


def test_stop_inside_the_day_loses_one_r() -> None:
    (t,) = run([(9, 9, 9, 9), (10, 10.5, 9.5, 10), (9.5, 9.6, 7.5, 8.2), (8, 8, 8, 8)])
    assert (t.reason, t.exit_price) == ("stop", 8.0)
    assert t.r_multiple == pytest.approx(-1.0)


def test_gap_through_the_stop_loses_more_than_planned() -> None:
    (t,) = run([(9, 9, 9, 9), (10, 10.5, 9.5, 10), (7, 7.5, 6.5, 7), (7, 7, 7, 7)])
    assert (t.reason, t.exit_price) == ("stop (gap)", 7.0)  # filled at the open, not at 8
    assert t.r_multiple == pytest.approx(-1.5)


def test_stop_is_assumed_first_when_both_levels_trade_on_one_day() -> None:
    (t,) = run([(9, 9, 9, 9), (10, 10.5, 9.5, 10), (10, 15, 7.9, 12), (12, 12, 12, 12)])
    assert t.reason == "stop"


def test_stop_can_hit_on_the_entry_day() -> None:
    (t,) = run([(9, 9, 9, 9), (10, 10.2, 7.5, 8), (8, 8, 8, 8)])
    assert (t.reason, t.holding_sessions) == ("stop", 1)


def test_time_exit_at_the_open_after_the_limit() -> None:
    quiet = [(10, 10.5, 9.5, 10)] * 6
    limited = Execution(2.0, 2.0, 3, 0.0, 0.0)
    (t,) = run([(9, 9, 9, 9), *quiet], execution=limited)
    # held days 1, 2, 3 -> exit at the open of day 4
    assert (t.reason, str(t.exit_date), t.exit_price) == ("time", "2024-01-05", 10.0)
    assert t.r_multiple == pytest.approx(0.0)


def test_signal_exit_fills_at_the_following_open() -> None:
    rows = [
        (9, 9, 9, 9),
        (10, 10.5, 9.5, 10),
        (10, 11, 10, 11),
        (11.5, 12, 11, 12),
        (12, 12, 12, 12),
    ]
    (t,) = run(rows, exits=(2,))
    assert (t.reason, str(t.exit_date), t.exit_price) == ("signal", "2024-01-04", 11.5)
    assert t.r_multiple == pytest.approx(0.75)


def test_costs_and_slippage_reduce_the_result() -> None:
    costly = Execution(2.0, 2.0, 10, slippage_bps=100.0, cost_bps_per_side=50.0)
    (t,) = run(
        [(9, 9, 9, 9), (10, 10.5, 9.5, 10), (10, 14.5, 10, 14), (14, 14, 14, 14)], execution=costly
    )
    # entry 10 x 1.01 = 10.10; exit 14 x 0.99 = 13.86
    # net = 13.86 x 0.995 - 10.10 x 1.005 = 13.7907 - 10.1505 = 3.6402
    assert t.entry_price == pytest.approx(10.10) and t.exit_price == pytest.approx(13.86)
    assert t.r_multiple == pytest.approx(3.6402 / 2)
    assert t.return_pct == pytest.approx(36.402)
    assert t.cost_pct == pytest.approx((4 - 3.6402) / 10 * 100)


def test_trade_still_open_at_the_end_is_reported_not_scored() -> None:
    (t,) = run([(9, 9, 9, 9), (10, 10.5, 9.5, 10), (10, 11, 10, 11)])
    assert t.reason == "open" and not t.closed and t.r_multiple is None


def test_signal_on_the_last_day_cannot_trade() -> None:
    assert run([(9, 9, 9, 9), (10, 10, 10, 10)], entries=(1,)) == []


def test_one_position_at_a_time_and_reentry_after_exit() -> None:
    rows = [
        (9, 9, 9, 9),
        (10, 10.5, 9.5, 10),
        (10, 14.5, 10, 14),
        (14, 14.5, 13.5, 14),
        (14, 18.5, 14, 18),
        (18, 18, 18, 18),
    ]
    trades = run(rows, entries=(0, 1, 2))
    # the day-1 signal is ignored (already in a trade); the day-2 signal re-enters at day 3
    assert [(str(t.entry_date), t.reason) for t in trades] == [
        ("2024-01-02", "target"),
        ("2024-01-04", "target"),
    ]


def test_no_trade_without_atr() -> None:
    assert run([(9, 9, 9, 9), (10, 14, 9, 10), (10, 10, 10, 10)], atr=float("nan")) == []
