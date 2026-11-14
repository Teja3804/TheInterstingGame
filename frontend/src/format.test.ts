import { describe, expect, it } from "vitest";
import {
  formatDate,
  formatFraction,
  formatInstant,
  formatLocal,
  formatNumber,
  formatPercent,
  signClass,
} from "./format";

describe("format", () => {
  it("shows a dash for missing values instead of a number", () => {
    expect(formatNumber(null)).toBe("–");
    expect(formatNumber(undefined)).toBe("–");
    expect(formatNumber(Number.NaN)).toBe("–");
    expect(formatFraction(null)).toBe("–");
    expect(formatPercent(undefined)).toBe("–");
  });

  it("formats numbers and signed percentages", () => {
    expect(formatNumber(1234.5)).toBe("1,234.50");
    expect(formatFraction(0.01234)).toBe("+1.23%");
    expect(formatFraction(-0.05)).toBe("−5.00%");
    expect(formatPercent(0)).toBe("0.00%");
    expect(signClass(0.2)).toBe("up");
    expect(signClass(-0.2)).toBe("down");
    expect(signClass(null)).toBe("");
  });

  it("keeps market-local times as sent and names the zone", () => {
    expect(formatLocal("2024-03-08T16:00:00-05:00", "America/New_York")).toBe(
      "8 Mar 2024, 16:00 America/New_York",
    );
    expect(formatLocal("2024-03-07T15:30:00+05:30", "Asia/Kolkata")).toBe(
      "7 Mar 2024, 15:30 Asia/Kolkata",
    );
    expect(formatLocal(null, "Asia/Kolkata")).toBe("–");
    expect(formatDate("2024-03-08")).toBe("8 Mar 2024");
  });

  it("converts stored UTC instants into the market zone", () => {
    expect(formatInstant("2024-03-09T12:00:00Z", "America/New_York")).toBe(
      "9 Mar 2024, 07:00 America/New_York",
    );
    expect(formatInstant("2024-03-09T12:00:00Z", "Asia/Kolkata")).toBe(
      "9 Mar 2024, 17:30 Asia/Kolkata",
    );
  });
});
