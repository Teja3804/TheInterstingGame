import { describe, expect, it } from "vitest";
import { viewPosition } from "./positionMath";

const dates = ["2024-03-04", "2024-03-05", "2024-03-06", "2024-03-07", "2024-03-08"];
const position = { id: "p1", symbol: "AAPL", quantity: 10, entry_price: 100, entry_date: "2024-03-05" };

describe("viewPosition", () => {
  it("values a position from the last close", () => {
    const view = viewPosition(position, 110, dates, 21, 1.2);
    expect(view.value).toBe(1100);
    expect(view.cost).toBe(1000);
    expect(view.pnl).toBe(100);
    expect(view.pnlFraction).toBeCloseTo(0.1);
    expect(view.hedgeValue).toBeCloseTo(1320); // 1100 x beta 1.2
  });

  it("counts completed sessions after the entry date", () => {
    const view = viewPosition(position, 110, dates, 3, null);
    expect(view.sessionsHeld).toBe(3); // 6, 7 and 8 March
    expect(view.pastTimeLimit).toBe(true);
    expect(view.hedgeValue).toBeNull();
    expect(viewPosition(position, 110, dates, 21, null).pastTimeLimit).toBe(false);
  });

  it("flags an entry older than the candles on hand", () => {
    const old = { ...position, entry_date: "2023-01-02" };
    const view = viewPosition(old, 90, dates, 21, 1);
    expect(view.sessionsHeld).toBe(5);
    expect(view.sessionsHeldIsMinimum).toBe(true);
    expect(view.pnl).toBe(-100);
  });
});
