"""Rule-based suggestions (CONTEXT.md sections 8 and 10). Pure.

These are the output of fixed, documented rules applied to the latest completed candle.
They are not predictions and carry no probability. "No trade" is always a valid outcome.
"""

from __future__ import annotations

from dataclasses import dataclass, field

BUY_CANDIDATE = "Buy candidate"
WATCH = "Watch"
NO_TRADE = "No trade"
REJECTED = "Rejected"
UNAVAILABLE = "Unavailable"

HOLD = "Hold"
HEDGE_OR_REDUCE = "Hold, consider hedging or reducing"
EXIT = "Exit"


@dataclass(frozen=True)
class Suggestion:
    action: str
    reasons: list[str] = field(default_factory=list)


def suggest_entry(
    score: float | None,
    rejections: list[str],
    regime: str,
    freshness: str,
    buy_threshold: float,
    watch_threshold: float,
) -> Suggestion:
    """What the rules say for someone who does NOT hold the stock."""
    if freshness != "fresh":
        return Suggestion(UNAVAILABLE, [f"data is {freshness}; refresh before relying on it"])
    if rejections:
        return Suggestion(REJECTED, rejections)
    if score is None:
        return Suggestion(UNAVAILABLE, ["score unavailable: not enough history"])
    if score >= buy_threshold:
        if regime == "Bearish":
            return Suggestion(
                WATCH,
                [
                    f"score {score:.0f} meets the buy threshold of {buy_threshold:g}, but the "
                    "market regime is Bearish, so new entries are held back"
                ],
            )
        reasons = [f"score {score:.0f} is at or above the buy threshold of {buy_threshold:g}"]
        if regime == "Uncertain":
            reasons.append("market regime is Uncertain: consider a smaller size")
        return Suggestion(BUY_CANDIDATE, reasons)
    if score >= watch_threshold:
        return Suggestion(
            WATCH,
            [
                f"score {score:.0f} is between the watch ({watch_threshold:g}) and buy "
                f"({buy_threshold:g}) thresholds"
            ],
        )
    return Suggestion(
        NO_TRADE, [f"score {score:.0f} is below the watch threshold of {watch_threshold:g}"]
    )


def advise_holder(
    close: float,
    sma_50: float | None,
    trailing_stop: float | None,
    score: float | None,
    regime: str,
    freshness: str,
    exit_below: float,
) -> Suggestion:
    """What the rules say for someone who DOES hold the stock. It deliberately ignores the
    purchase price: whether to keep holding depends on where the stock is now."""
    if freshness != "fresh":
        return Suggestion(UNAVAILABLE, [f"data is {freshness}; refresh before relying on it"])
    exits: list[str] = []
    if trailing_stop is not None and close < trailing_stop:
        exits.append(f"close {close:.2f} is below the trailing stop {trailing_stop:.2f}")
    if sma_50 is not None and close < sma_50:
        exits.append(
            f"close {close:.2f} is below the 50-day average {sma_50:.2f} (trend invalidated)"
        )
    if score is not None and score < exit_below:
        exits.append(f"score {score:.0f} is below the exit level of {exit_below:g}")
    if exits:
        return Suggestion(EXIT, exits)
    if regime == "Bearish":
        return Suggestion(
            HEDGE_OR_REDUCE,
            ["the stock's own exit rules have not triggered, but the market regime is Bearish"],
        )
    reasons = ["no exit rule has triggered"]
    if trailing_stop is not None:
        reasons.append(f"trailing stop is at {trailing_stop:.2f}")
    if regime == "Uncertain":
        reasons.append("market regime is Uncertain")
    return Suggestion(HOLD, reasons)
