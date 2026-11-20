import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { Quote } from "../api";
import { LatestPrice } from "./LatestPrice";

const ZONE = "America/New_York";
// Synthetic values for display tests; not market data.
const base: Quote = {
  symbol: "TEST",
  is_benchmark: false,
  currency: "USD",
  price: 101.25,
  change_pct: 1.25,
  kind: "during_session",
  market_time_local: "2024-03-08T12:45:00-05:00",
  warnings: [],
  last_error: null,
};

describe("LatestPrice", () => {
  afterEach(cleanup);

  it("shows price, currency, change and the delayed time in the market zone", () => {
    render(<LatestPrice quote={base} zone={ZONE} />);
    expect(screen.getByText("101.25")).toBeTruthy();
    expect(screen.getByText("USD")).toBeTruthy();
    expect(screen.getByText("+1.25% today")).toBeTruthy();
    expect(screen.getByText("Delayed price, 8 Mar 2024, 12:45 America/New_York")).toBeTruthy();
  });

  it("calls a quote after the session a closing price", () => {
    render(<LatestPrice quote={{ ...base, kind: "after_close" }} zone={ZONE} />);
    expect(screen.getByText(/^Closing price, 8 Mar 2024/)).toBeTruthy();
  });

  it("says why a price is unavailable instead of showing a number", () => {
    const missing = { ...base, price: null, unavailable_reason: "no quote fetched yet" };
    render(<LatestPrice quote={missing} zone={ZONE} />);
    expect(screen.getByText(/Latest price unavailable: no quote fetched yet/)).toBeTruthy();
    expect(screen.queryByText("101.25")).toBeNull();
  });

  it("flags warnings and a failed refresh", () => {
    const flagged = {
      ...base,
      warnings: ["close_mismatch: quote differs by +1.00%"],
      last_error: "TEST: rate limited",
    };
    render(<LatestPrice quote={flagged} zone={ZONE} />);
    expect(screen.getByText("Check: close mismatch")).toBeTruthy();
    expect(screen.getByText(/Last refresh failed/)).toBeTruthy();
  });
});
