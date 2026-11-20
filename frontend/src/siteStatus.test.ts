import { describe, expect, it } from "vitest";
import type { StatusResponse } from "./api";
import { updateIsLate } from "./siteStatus";

const BUILT = "2024-03-08T18:00:00Z";
const minutesAfter = (m: number) => Date.parse(BUILT) + m * 60000;

function status(open: boolean, scheduled = true): StatusResponse {
  return {
    snapshot: {
      exported_at_utc: BUILT,
      note: "",
      scheduled,
      update_every_minutes: 15,
      stale_after_minutes: 60,
    },
    markets: [{ clock: { is_open: open } }],
  } as unknown as StatusResponse;
}

describe("updateIsLate", () => {
  it("allows the configured delay while a market was open at the last update", () => {
    expect(updateIsLate(status(true), minutesAfter(59))).toBe(false);
    expect(updateIsLate(status(true), minutesAfter(61))).toBe(true);
  });

  it("allows a quiet night while markets were closed, but not more than a day", () => {
    expect(updateIsLate(status(false), minutesAfter(12 * 60))).toBe(false);
    expect(updateIsLate(status(false), minutesAfter(27 * 60))).toBe(true);
  });

  it("never warns for a one-off snapshot", () => {
    expect(updateIsLate(status(true, false), minutesAfter(10_000))).toBe(false);
    expect(updateIsLate(null, minutesAfter(10_000))).toBe(false);
  });
});
