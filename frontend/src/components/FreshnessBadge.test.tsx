import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FreshnessBadge } from "./FreshnessBadge";

describe("FreshnessBadge", () => {
  it("labels each state in words, not colour alone", () => {
    const { rerender } = render(<FreshnessBadge state="fresh" />);
    expect(screen.getByText("Fresh")).toHaveClass("badge-fresh");
    rerender(<FreshnessBadge state="stale" />);
    expect(screen.getByText("Stale")).toHaveClass("badge-stale");
    rerender(<FreshnessBadge state="missing" />);
    expect(screen.getByText("No data")).toBeInTheDocument();
  });
});
