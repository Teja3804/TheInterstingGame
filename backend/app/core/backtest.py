"""Trade simulator shared by every strategy (CONTEXT.md section 14). Pure.

Execution model
- A signal is read at the close of day D; the order fills at the OPEN of day D+1.
- Initial stop = entry - stop_atr_multiple x ATR(D). Target = entry + target_r x risk.
- On each day held: if the open is already through the stop, the trade exits at the open
  (overnight gap: the loss is larger than planned). Otherwise a low at or below the stop
  exits at the stop. If stop and target are both touched on one day, the stop is assumed
  to come first.
- An exit signal at the close, or reaching max_holding_sessions, exits at the next open.
- Slippage worsens every fill; costs are charged per side. Both are estimates from config.
- One position per symbol at a time. A trade still open at the end of the data is reported
  separately and left out of the statistics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Execution:
    stop_atr_multiple: float
    target_r_multiple: float | None
    max_holding_sessions: int
    slippage_bps: float
    cost_bps_per_side: float


@dataclass(frozen=True)
class Trade:
    symbol: str
    signal_date: object
    entry_date: object
    entry_price: float
    stop_price: float
    exit_date: object | None
    exit_price: float | None
    reason: str  # stop | stop (gap) | target | signal | time | open
    holding_sessions: int
    r_multiple: float | None  # net result divided by the planned risk per share
    return_pct: float | None  # net result as % of the entry value
    cost_pct: float | None  # costs and slippage as % of the entry value
    planned_risk_pct: float  # (entry - stop) / entry x 100

    @property
    def closed(self) -> bool:
        return self.exit_date is not None


def simulate(
    symbol: str,
    frame: pd.DataFrame,
    entries: pd.Series,
    exits: pd.Series | None,
    execution: Execution,
) -> list[Trade]:
    """`frame` needs adjusted open/high/low/close and `atr`, indexed by date, oldest first.
    `entries` / `exits` are booleans known at each day's close."""
    opens = frame["open"].to_numpy(dtype=float)
    highs = frame["high"].to_numpy(dtype=float)
    lows = frame["low"].to_numpy(dtype=float)
    closes = frame["close"].to_numpy(dtype=float)
    atrs = frame["atr"].to_numpy(dtype=float)
    dates = list(frame.index)
    enter = entries.fillna(False).to_numpy(dtype=bool)
    leave = exits.fillna(False).to_numpy(dtype=bool) if exits is not None else None
    slip = execution.slippage_bps / 10_000.0
    cost = execution.cost_bps_per_side / 10_000.0
    count = len(dates)
    trades: list[Trade] = []

    i = 0
    while i < count - 1:
        if not (enter[i] and math.isfinite(atrs[i]) and atrs[i] > 0):
            i += 1
            continue
        start = i + 1
        raw_entry = opens[start]
        entry = raw_entry * (1 + slip)
        risk = execution.stop_atr_multiple * atrs[i]
        stop = raw_entry - risk
        if stop <= 0:
            i += 1
            continue
        target = (
            raw_entry + execution.target_r_multiple * risk
            if execution.target_r_multiple is not None
            else None
        )

        exit_index: int | None = None
        exit_raw = math.nan
        reason = "open"
        j = start
        while j < count:
            if j > start and opens[j] <= stop:
                exit_index, exit_raw, reason = j, opens[j], "stop (gap)"
            elif lows[j] <= stop:
                exit_index, exit_raw, reason = j, stop, "stop"
            elif target is not None and j > start and opens[j] >= target:
                exit_index, exit_raw, reason = j, opens[j], "target"
            elif target is not None and highs[j] >= target:
                exit_index, exit_raw, reason = j, target, "target"
            if exit_index is not None:
                break
            held = j - start + 1
            signal_exit = leave is not None and leave[j]
            if signal_exit or held >= execution.max_holding_sessions:
                if j + 1 < count:
                    exit_index, exit_raw = j + 1, opens[j + 1]
                    reason = "signal" if signal_exit else "time"
                break
            j += 1

        planned_risk_pct = risk / raw_entry * 100.0
        if exit_index is None:
            trades.append(
                Trade(
                    symbol,
                    dates[i],
                    dates[start],
                    entry,
                    stop,
                    None,
                    None,
                    "open",
                    count - start,
                    None,
                    None,
                    None,
                    planned_risk_pct,
                )
            )
            break
        exit_price = exit_raw * (1 - slip)
        net = exit_price * (1 - cost) - entry * (1 + cost)
        gross = exit_raw - raw_entry
        trades.append(
            Trade(
                symbol=symbol,
                signal_date=dates[i],
                entry_date=dates[start],
                entry_price=entry,
                stop_price=stop,
                exit_date=dates[exit_index],
                exit_price=exit_price,
                reason=reason,
                holding_sessions=exit_index - start + 1,
                r_multiple=net / risk,
                return_pct=net / raw_entry * 100.0,
                cost_pct=(gross - net) / raw_entry * 100.0,
                planned_risk_pct=planned_risk_pct,
            )
        )
        # Flat again at the exit day's close: the earliest new signal is that same close.
        i = exit_index
    _ = closes  # closes are part of the documented input contract
    return trades
