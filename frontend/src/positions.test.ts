import { beforeEach, describe, expect, it } from "vitest";
import { positionStore, type Position } from "./positions";

const sample: Position = {
  id: "p1",
  symbol: "AAPL",
  quantity: 5,
  entry_price: 100,
  entry_date: "2024-03-05",
};

describe("position store without a hosted database", () => {
  beforeEach(() => localStorage.clear());

  it("saves, updates, lists and removes positions in the browser", async () => {
    const store = await positionStore();
    expect(store.kind).toBe("browser");
    const seen: Position[][] = [];
    const stop = store.subscribe((positions) => seen.push(positions));
    expect(seen.at(-1)).toEqual([]);

    await store.save(sample);
    await store.save({ ...sample, quantity: 8 }); // same id replaces
    expect(seen.at(-1)).toEqual([{ ...sample, quantity: 8 }]);

    await store.remove("p1");
    expect(seen.at(-1)).toEqual([]);
    stop();
  });

  it("ignores stored rows that are not valid positions", async () => {
    localStorage.setItem(
      "sti.positions.v1",
      JSON.stringify([{ id: "x", symbol: "AAPL", quantity: -1, entry_price: 5, entry_date: "2024-01-01" }, sample]),
    );
    const store = await positionStore();
    let latest: Position[] = [];
    store.subscribe((positions) => (latest = positions))();
    expect(latest).toEqual([sample]);
  });
});
