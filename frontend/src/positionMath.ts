// The only arithmetic done in the page: turning a hand-entered position (quantity and
// entry price) into values using figures the backend already computed. Kept in one small,
// tested file because the position lives with the viewer, not on the server.

import type { Position } from "./positions";

export interface PositionView {
  value: number;
  cost: number;
  pnl: number;
  pnlFraction: number;
  sessionsHeld: number;
  sessionsHeldIsMinimum: boolean; // entry is older than the candles on hand
  pastTimeLimit: boolean;
  hedgeValue: number | null; // index exposure with the same market sensitivity
}

export function viewPosition(
  position: Position,
  lastClose: number,
  candleDates: string[],
  maxHoldingSessions: number,
  beta: number | null,
): PositionView {
  const value = position.quantity * lastClose;
  const cost = position.quantity * position.entry_price;
  const sessionsHeld = candleDates.filter((day) => day > position.entry_date).length;
  const olderThanData = candleDates.length > 0 && position.entry_date < candleDates[0];
  return {
    value,
    cost,
    pnl: value - cost,
    pnlFraction: lastClose / position.entry_price - 1,
    sessionsHeld,
    sessionsHeldIsMinimum: olderThanData,
    pastTimeLimit: sessionsHeld >= maxHoldingSessions,
    hedgeValue: beta === null ? null : value * beta,
  };
}
