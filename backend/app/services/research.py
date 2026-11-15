"""Builds the three screens' data from stored candles: stock insights, risk analysis of
the current strategy, and the strategy comparison.

All maths lives in app.core. This module loads data, runs the pure functions and labels
every result with the candle date, fetch time and source it came from. Every performance
number produced here is a BACKTEST.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.config import MarketConfig, Settings
from app.core import advice, freshness, regime, scoring, sizing, stats, strategies
from app.core import indicators as ind
from app.core.backtest import Execution, Trade, simulate
from app.services.analysis import AnalysisService, SymbolData, iso_utc
from app.services.calendars import MarketCalendar

LABEL = "BACKTEST"

COMPONENT_TEXT: dict[str, tuple[str, str]] = {
    "trend": (
        "Trend strength",
        "25 points each for: close above SMA 50, close above SMA 200, SMA 50 above SMA 200, "
        "SMA 50 higher than 20 sessions ago.",
    ),
    "relative_strength": (
        "Relative strength",
        "20-session return minus the benchmark's, scaled from -10% (0) to +10% (100).",
    ),
    "momentum": (
        "Momentum",
        "Average of: RSI 14 band (50 to 70 = 100, 40 to 80 = 50, else 0), MACD histogram "
        "above zero, positive 20-session return.",
    ),
    "volume": (
        "Volume confirmation",
        "5-session average of volume relative to the prior 20 sessions, scaled from 0.5 (0) "
        "to 1.5 (100).",
    ),
    "sector": (
        "Sector alignment",
        "The sector reference's 20-session return minus the benchmark's, scaled from -5% (0) "
        "to +5% (100).",
    ),
    "reward_risk": (
        "Reward/risk quality",
        "Room to the nearest resistance divided by the stop distance, scaled from 1 (0) to "
        "3 (100). With nothing overhead the planned target is used.",
    ),
}

REJECTION_TEXT = {
    "insufficient_history": "not enough history for the 200-session average",
    "insufficient_liquidity": "average traded value is below the configured minimum",
    "too_volatile": "daily ATR is above the configured maximum share of price",
}


def _num(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _day(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, dt.date) else (str(value) if value else None)


@dataclass
class SymbolResearch:
    data: SymbolData
    sector: str | None
    sector_reference: str | None
    sector_available: bool
    frame: pd.DataFrame  # adjusted OHLC + atr + score + rejected, indexed by date
    scores: pd.DataFrame
    rejections: pd.DataFrame


@dataclass
class MarketResearch:
    code: str
    config: MarketConfig
    calendar: MarketCalendar
    last_completed: dt.date | None
    benchmark: SymbolData
    regimes: pd.DataFrame  # empty when the benchmark has no data
    symbols: dict[str, SymbolResearch] = field(default_factory=dict)
    trades: dict[str, list[Trade]] = field(default_factory=dict)  # strategy key -> trades


class ResearchService:
    def __init__(self, settings: Settings, analysis: AnalysisService) -> None:
        self._settings = settings
        self._analysis = analysis
        self._cache_key: tuple[Any, ...] | None = None
        self._cache: dict[str, MarketResearch] = {}

    # -- construction ------------------------------------------------------------------

    def _score_params(self) -> scoring.ScoreParams:
        c = self._settings.scoring.components
        plan = self._settings.risk.plan
        sr = self._settings.indicators.support_resistance
        return scoring.ScoreParams(
            weights=self._settings.scoring.weights,
            slope_sessions=int(c["trend"]["slope_sessions"]),
            rs_sessions=int(c["relative_strength"]["sessions"]),
            rs_floor_pct=float(c["relative_strength"]["floor_pct"]),
            rs_cap_pct=float(c["relative_strength"]["cap_pct"]),
            momentum_return_sessions=int(c["momentum"]["return_sessions"]),
            rsi_best=(float(c["momentum"]["rsi_best"][0]), float(c["momentum"]["rsi_best"][1])),
            rsi_ok=(float(c["momentum"]["rsi_ok"][0]), float(c["momentum"]["rsi_ok"][1])),
            volume_average_sessions=int(c["volume"]["average_sessions"]),
            volume_floor=float(c["volume"]["floor"]),
            volume_cap=float(c["volume"]["cap"]),
            sector_sessions=int(c["sector"]["sessions"]),
            sector_floor_pct=float(c["sector"]["floor_pct"]),
            sector_cap_pct=float(c["sector"]["cap_pct"]),
            rr_floor=float(c["reward_risk"]["floor"]),
            rr_cap=float(c["reward_risk"]["cap"]),
            stop_atr_multiple=plan.stop_atr_multiple,
            target_r_multiple=plan.target_r_multiple,
            pivot_window=sr.pivot_window,
            pivot_lookback=sr.lookback_sessions,
        )

    def _execution(self, market: str) -> Execution:
        plan, cost = self._settings.risk.plan, self._settings.risk.costs[market]
        return Execution(
            stop_atr_multiple=plan.stop_atr_multiple,
            target_r_multiple=plan.target_r_multiple,
            max_holding_sessions=plan.max_holding_sessions,
            slippage_bps=cost.slippage_bps,
            cost_bps_per_side=cost.cost_bps_per_side,
        )

    def _catalogue(self) -> list[strategies.StrategySpec]:
        t = self._settings.scoring.thresholds
        return strategies.catalogue(t.buy_candidate, t.exit_below)

    def build(self, db: Session, now: dt.datetime) -> dict[str, MarketResearch]:
        """Everything the screens need, cached until new data is stored or a session ends."""
        ranges = self._analysis.stored_ranges(db)
        statuses = self._analysis.fetch_status(db)
        stamp = max(
            (s.last_success_at for s in statuses.values() if s.last_success_at), default=None
        )
        calendars = {code: self._analysis.calendar(code) for code in self._settings.markets}
        completed = {code: cal.last_completed_session(now) for code, cal in calendars.items()}
        key = (stamp, tuple(sorted(completed.items(), key=str)), len(ranges))
        if key == self._cache_key:
            return self._cache

        params = self._score_params()
        result: dict[str, MarketResearch] = {}
        for code, market in self._settings.markets.items():
            benchmark = self._analysis.load(db, market.relative_strength_benchmark, code)
            ind_cfg, reg_cfg = self._settings.indicators, self._settings.scoring.regime
            regimes = (
                pd.DataFrame()
                if benchmark.empty
                else regime.regime_frame(
                    benchmark.adjusted["close"],
                    ind_cfg.volatility_window,
                    ind_cfg.trading_days_per_year,
                    reg_cfg.high_volatility_percentile,
                    reg_cfg.volatility_lookback_sessions,
                )
            )
            research = MarketResearch(
                code, market, calendars[code], completed[code], benchmark, regimes
            )
            references: dict[str, SymbolData] = {}
            for symbol in market.symbols:
                data = self._analysis.load(db, symbol, code)
                if data.empty:
                    continue
                profile = self._analysis.profile(db, symbol)
                sector = profile["sector"] if profile else None
                reference = market.sector_references.get(sector) if sector else None
                sector_close = None
                if reference:
                    if reference not in references:
                        references[reference] = self._analysis.load(db, reference, code)
                    ref = references[reference]
                    # A reference needs enough history to be usable at all.
                    if not ref.empty and len(ref.frame) > params.sector_sessions + 1:
                        sector_close = ref.adjusted["close"]
                bench_close = None if benchmark.empty else benchmark.adjusted["close"]
                scores = scoring.score_frame(
                    data.adjusted, data.frame["volume"], bench_close, sector_close, params
                )
                rejections = scoring.rejection_frame(
                    data.adjusted,
                    data.frame["close"],
                    data.frame["volume"],
                    scores["input_atr_pct"],
                    self._settings.scoring.rejections.min_sessions,
                    self._settings.scoring.rejections.min_avg_traded_value[code],
                    self._settings.scoring.rejections.max_atr_pct,
                )
                frame = data.adjusted.copy()
                frame["atr"] = scores["input_atr"]
                frame["score"] = scores["score"]
                frame["rejected"] = rejections["rejected"]
                research.symbols[symbol] = SymbolResearch(
                    data, sector, reference, sector_close is not None, frame, scores, rejections
                )

            execution = self._execution(code)
            for spec in self._catalogue():
                trades: list[Trade] = []
                for symbol, item in research.symbols.items():
                    entries, exits = spec.build(item.frame)
                    trades.extend(simulate(symbol, item.frame, entries, exits, execution))
                research.trades[spec.key] = trades
            result[code] = research

        self._cache_key, self._cache = key, result
        return result

    # -- shared pieces -----------------------------------------------------------------

    def _regime_now(self, market: MarketResearch) -> dict[str, Any]:
        symbol = market.config.relative_strength_benchmark
        if market.regimes.empty:
            return {
                "label": regime.UNCERTAIN,
                "benchmark": symbol,
                "as_of": None,
                "evidence": [f"no stored data for {symbol}"],
            }
        last = market.regimes.iloc[-1]
        evidence = [
            f"{symbol} close {last['close']:,.2f}",
            "SMA 50 " + (f"{last['sma_50']:,.2f}" if _num(last["sma_50"]) else "unavailable"),
            "SMA 200 " + (f"{last['sma_200']:,.2f}" if _num(last["sma_200"]) else "unavailable"),
        ]
        if _num(last["volatility"]) is not None:
            rank = _num(last["volatility_percentile"])
            evidence.append(
                f"annualised volatility {last['volatility'] * 100:.1f}%"
                + (f", at the {rank:.0f}th percentile of its recent history" if rank else "")
            )
        return {
            "label": str(last["regime"]),
            "benchmark": symbol,
            "as_of": _day(market.regimes.index[-1]),
            "evidence": evidence,
            "rule": (
                "Bullish: close above SMA 200 and SMA 50 above SMA 200. Bearish: both below. "
                "Uncertain: volatility in its top "
                f"{100 - self._settings.scoring.regime.high_volatility_percentile:.0f}% or too "
                "little history. Otherwise Neutral."
            ),
        }

    def _entry_suggestion(
        self, market: MarketResearch, item: SymbolResearch, regime_label: str
    ) -> tuple[advice.Suggestion, float | None, list[str], str]:
        latest: dt.date = item.data.frame.index[-1]
        state = freshness.classify(latest, market.last_completed)
        score = _num(item.scores["score"].iloc[-1])
        flags = item.rejections.iloc[-1]
        reasons = [text for key, text in REJECTION_TEXT.items() if bool(flags[key])]
        t = self._settings.scoring.thresholds
        suggestion = advice.suggest_entry(
            score, reasons, regime_label, state, t.buy_candidate, t.watch
        )
        return suggestion, score, reasons, state

    def _trailing_stop(self, item: SymbolResearch) -> float | None:
        plan = self._settings.risk.plan
        close = item.frame["close"]
        if len(close) < plan.trailing_lookback_sessions:
            return None
        atr = _num(item.frame["atr"].iloc[-1])
        if atr is None:
            return None
        highest = float(close.tail(plan.trailing_lookback_sessions).max())
        return highest - plan.trailing_atr_multiple * atr

    # -- screen 1: stocks --------------------------------------------------------------

    def stocks(self, db: Session, now: dt.datetime) -> dict[str, Any]:
        built = self.build(db, now)
        markets: list[dict[str, Any]] = []
        for code, market in built.items():
            regime_now = self._regime_now(market)
            rows: list[dict[str, Any]] = []
            for symbol in market.config.symbols:
                item = market.symbols.get(symbol)
                profile = self._analysis.profile(db, symbol)
                if item is None:
                    empty = SymbolData(symbol, code, pd.DataFrame(), pd.DataFrame())
                    row = self._analysis.provenance(empty, market.calendar, market.last_completed)
                    row |= {
                        "name": profile["name"] if profile else None,
                        "sector": profile["sector"] if profile else None,
                        "score": None,
                        "suggestion": {
                            "action": advice.UNAVAILABLE,
                            "reasons": ["no data stored; run a refresh"],
                        },
                        "values": {},
                    }
                    rows.append(row)
                    continue
                suggestion, score, _, _ = self._entry_suggestion(market, item, regime_now["label"])
                close = item.frame["close"]
                row = self._analysis.provenance(item.data, market.calendar, market.last_completed)
                row |= {
                    "name": profile["name"] if profile else None,
                    "sector": item.sector,
                    "score": score,
                    "suggestion": {"action": suggestion.action, "reasons": suggestion.reasons},
                    "values": {
                        "last_close": _num(item.data.frame["close"].iloc[-1]),
                        "return_1": _num(ind.session_return(close, 1).iloc[-1]),
                        "return_5": _num(ind.session_return(close, 5).iloc[-1]),
                        "return_20": _num(ind.session_return(close, 20).iloc[-1]),
                        "rsi": _num(item.scores["input_rsi"].iloc[-1]),
                        "atr_pct": _num(item.scores["input_atr_pct"].iloc[-1]),
                    },
                    "spark": [_num(v) for v in close.tail(60).to_numpy()],
                }
                rows.append(row)
            markets.append(
                {
                    "code": code,
                    "name": market.config.name,
                    "currency": market.config.currency,
                    "timezone": market.config.timezone,
                    "last_completed_session": _day(market.last_completed),
                    "regime": regime_now,
                    "rows": rows,
                }
            )
        t = self._settings.scoring.thresholds
        return {
            "generated_at_utc": iso_utc(now),
            "thresholds": t.model_dump(),
            "note": (
                "Suggestions come from fixed rules applied to the latest completed daily "
                "candle. A score is a ranking from 0 to 100, not a probability of profit."
            ),
            "markets": markets,
        }

    def insight(self, db: Session, now: dt.datetime, symbol: str) -> dict[str, Any] | None:
        """Full reasoning for one watchlist stock. None for symbols that are not scored."""
        built = self.build(db, now)
        code = self._settings.market_of(symbol)
        if code is None or symbol not in self._settings.markets[code].symbols:
            return None
        market = built[code]
        item = market.symbols.get(symbol)
        if item is None:
            return {"available": False, "reason": "no data stored; run a refresh"}

        regime_now = self._regime_now(market)
        suggestion, score, rejection_reasons, state = self._entry_suggestion(
            market, item, regime_now["label"]
        )
        last = item.scores.iloc[-1]
        weights = self._settings.scoring.weights
        inputs: dict[str, list[tuple[str, Any, str]]] = {
            "trend": [
                ("Close (adjusted)", item.frame["close"].iloc[-1], "price"),
                ("SMA 50", last["input_sma_50"], "price"),
                ("SMA 200", last["input_sma_200"], "price"),
            ],
            "relative_strength": [
                (
                    f"Return minus {market.config.relative_strength_benchmark}, 20 sessions",
                    last["input_excess_return_pct"],
                    "pct",
                )
            ],
            "momentum": [
                ("RSI 14", last["input_rsi"], "number"),
                ("MACD histogram", last["input_macd_histogram"], "number"),
                ("20-session return", last["input_return_pct"], "pct"),
            ],
            "volume": [
                ("Average relative volume, 5 sessions", last["input_avg_relative_volume"], "number")
            ],
            "sector": [
                (
                    f"{item.sector_reference or 'sector'} return minus benchmark, 20 sessions",
                    last["input_sector_excess_pct"],
                    "pct",
                )
            ],
            "reward_risk": [
                ("Reward/risk", last["input_reward_risk"], "number"),
                ("Nearest resistance", last["input_nearest_resistance"], "price"),
            ],
        }
        components: list[dict[str, Any]] = []
        for key in scoring.COMPONENTS:
            value = _num(last[key])
            reason = None
            if value is None:
                if key == "sector":
                    if item.sector is None:
                        reason = "unavailable: the data source gave no sector for this stock"
                    elif item.sector_reference is None:
                        reason = f"unavailable: no sector reference configured for {item.sector}"
                    else:
                        reason = f"unavailable: no usable data for {item.sector_reference}"
                elif key == "relative_strength":
                    reason = "unavailable: no benchmark candle for this date"
                else:
                    reason = "unavailable: not enough history"
            components.append(
                {
                    "key": key,
                    "label": COMPONENT_TEXT[key][0],
                    "formula": COMPONENT_TEXT[key][1],
                    "weight": weights[key],
                    "score": value,
                    "unavailable_reason": reason,
                    "inputs": [
                        {"label": label, "value": _num(v), "kind": kind}
                        for label, v, kind in inputs[key]
                    ],
                }
            )

        bullish = [
            f"{c['label']} scores {c['score']:.0f}" for c in components if (c["score"] or 0) >= 70
        ]
        bearish = [
            f"{c['label']} scores {c['score']:.0f}"
            for c in components
            if c["score"] is not None and c["score"] <= 30
        ]
        bearish.extend(rejection_reasons)
        if regime_now["label"] in (regime.BEARISH, regime.UNCERTAIN):
            bearish.append(f"market regime is {regime_now['label']}")
        elif regime_now["label"] == regime.BULLISH:
            bullish.append("market regime is Bullish")

        plan = self._plan(market, item)
        trailing = self._trailing_stop(item)
        holder = advice.advise_holder(
            float(item.frame["close"].iloc[-1]),
            _num(last["input_sma_50"]),
            trailing,
            score,
            regime_now["label"],
            state,
            self._settings.scoring.thresholds.exit_below,
        )
        ranked = sorted(
            (
                (other, _num(research.scores["score"].iloc[-1]))
                for other, research in market.symbols.items()
                if other != symbol and not bool(research.rejections["rejected"].iloc[-1])
            ),
            key=lambda pair: -(pair[1] or -1),
        )
        history = [t for t in market.trades["score_model"] if t.symbol == symbol]
        return {
            "available": True,
            "label_note": "Rule-based output on the latest completed candle. Not a prediction.",
            "regime": regime_now,
            "suggestion": {"action": suggestion.action, "reasons": suggestion.reasons},
            "score": score,
            "weight_used": _num(last["weight_used"]),
            "components": components,
            "rejections": rejection_reasons,
            "not_checked": [
                "Earnings dates and company news are not available in this version, so "
                "event risk inside the holding window is NOT checked."
            ],
            "bullish": bullish,
            "bearish": bearish,
            "plan": plan,
            "if_held": {
                "action": holder.action,
                "reasons": holder.reasons,
                "trailing_stop": trailing,
                "sma_50": _num(last["input_sma_50"]),
                "max_holding_sessions": self._settings.risk.plan.max_holding_sessions,
                "options": [
                    "Exit to cash",
                    "Reduce the position",
                    "Replace with a stronger candidate (see alternatives)",
                    f"Move to the index ETF ({market.config.hedge_instrument})",
                ],
            },
            "hedge": self._hedge(db, market, item),
            "alternatives": [
                {"symbol": other, "score": value}
                for other, value in ranked[:3]
                if value is not None
            ],
            "backtest_history": {
                "label": LABEL,
                "strategy": "Scoring model (current)",
                "summary": stats.summarise(
                    history, self._settings.risk.limits.risk_per_trade_pct
                ).as_dict(),
                "recent": [self._trade_json(t) for t in history[-6:]][::-1],
            },
        }

    def _plan(self, market: MarketResearch, item: SymbolResearch) -> dict[str, Any] | None:
        plan_cfg, limits = self._settings.risk.plan, self._settings.risk.limits
        atr = _num(item.frame["atr"].iloc[-1])
        if atr is None:
            return None
        # Reference prices are the tradable (split-adjusted) close, not the dividend-adjusted one.
        entry = float(item.data.frame["close"].iloc[-1])
        scale_to_raw = entry / float(item.frame["close"].iloc[-1])
        risk = plan_cfg.stop_atr_multiple * atr * scale_to_raw
        stop = entry - risk
        if stop <= 0:
            return None
        target = entry + plan_cfg.target_r_multiple * risk
        portfolio = self._settings.risk.portfolio[market.code]
        size = sizing.position_size(
            sizing.SizingInput(
                equity=portfolio.equity,
                cash=portfolio.cash,
                entry=entry,
                stop=stop,
                risk_per_trade_pct=limits.risk_per_trade_pct,
                max_stock_pct=limits.max_stock_pct,
                max_sector_pct=limits.max_sector_pct,
                max_open_risk_pct=limits.max_open_risk_pct,
                lot_size=portfolio.lot_size,
            )
        )
        cost = self._settings.risk.costs[market.code]
        round_trip_pct = 2 * (cost.cost_bps_per_side + cost.slippage_bps) / 100.0
        gap_r = self._settings.risk.analysis.stress.gap_r_multiple
        return {
            "entry_reference": entry,
            "entry_condition": "Next session's open, only if the suggestion still holds after that day's close.",
            "stop": stop,
            "stop_rule": f"{plan_cfg.stop_atr_multiple:g} x ATR 14 below the entry",
            "target": target,
            "target_rule": f"{plan_cfg.target_r_multiple:g} x the stop distance above the entry",
            "risk_per_share": risk,
            "risk_pct_of_price": risk / entry * 100.0,
            "reward_risk_after_costs": ((target - entry) / entry * 100.0 - round_trip_pct)
            / (risk / entry * 100.0 + round_trip_pct),
            "estimated_round_trip_cost_pct": round_trip_pct,
            "max_holding_sessions": plan_cfg.max_holding_sessions,
            "sizing": {
                "example_equity": portfolio.equity,
                "shares": size.shares,
                "binding_constraint": size.binding_constraint,
                "position_value": size.position_value,
                "risk_amount": size.risk_amount,
                "risk_budget": size.risk_budget,
                "limits": size.limits,
                "gap_loss_amount": size.shares * risk * gap_r,
                "gap_r_multiple": gap_r,
                "note": "Uses the EXAMPLE portfolio size in config/risk.yaml. Replace it with yours.",
            },
            "scenarios": [
                {
                    "name": "Bullish",
                    "text": f"Price reaches the target {target:,.2f} within "
                    f"{plan_cfg.max_holding_sessions} sessions: take profit.",
                    "changes_the_plan": f"A close below the 50-day average or a score under "
                    f"{self._settings.scoring.thresholds.exit_below:g} before then.",
                },
                {
                    "name": "Base",
                    "text": f"Price stays between {stop:,.2f} and {target:,.2f}: exit at the "
                    f"open after {plan_cfg.max_holding_sessions} sessions (time-based exit).",
                    "changes_the_plan": "The market regime turning Bearish: consider reducing or hedging.",
                },
                {
                    "name": "Bearish",
                    "text": f"Price trades at or below the stop {stop:,.2f}: exit. If it opens "
                    "below the stop, the loss is taken at the open and is larger than planned.",
                    "changes_the_plan": "Nothing: the stop is not moved down and the position is never averaged down.",
                },
            ],
        }

    def _hedge(self, db: Session, market: MarketResearch, item: SymbolResearch) -> dict[str, Any]:
        instrument = market.config.hedge_instrument
        sessions = self._settings.risk.hedge.beta_sessions
        base: dict[str, Any] = {
            "instrument": instrument,
            "benchmark": market.config.relative_strength_benchmark,
            "beta_sessions": sessions,
            "limitations": [
                "Informational only: this system never places a hedge, and shorting or "
                "options are out of scope.",
                "Beta is measured on past returns and changes over time.",
                "A hedge sized by beta removes index-driven moves only; company-specific risk remains.",
                "Hedging has costs (spreads, borrow or margin) that are not estimated here.",
            ],
        }
        if market.benchmark.empty:
            return base | {"beta": None, "unavailable_reason": "no benchmark data stored"}
        measured = ind.beta(item.frame["close"], market.benchmark.adjusted["close"], sessions)
        if measured is None:
            return base | {"beta": None, "unavailable_reason": "not enough overlapping history"}
        value, correlation = measured
        hedge_data = self._analysis.load(db, instrument, market.code) if instrument else None
        return base | {
            "beta": value,
            "correlation": correlation,
            "variance_explained_pct": correlation * correlation * 100.0,
            "hedge_value_per_100": value * 100.0,
            "instrument_last_close": (
                _num(hedge_data.frame["close"].iloc[-1])
                if hedge_data and not hedge_data.empty
                else None
            ),
        }

    @staticmethod
    def _trade_json(trade: Trade) -> dict[str, Any]:
        return {
            "symbol": trade.symbol,
            "entry_date": _day(trade.entry_date),
            "exit_date": _day(trade.exit_date),
            "reason": trade.reason,
            "holding_sessions": trade.holding_sessions,
            "r_multiple": trade.r_multiple,
            "return_pct": trade.return_pct,
        }

    # -- screen 2: risk analysis of the current strategy --------------------------------

    def _lookup(self, market: MarketResearch, column: str, day: Any) -> Any:
        """Benchmark-derived value known at `day` (the latest row on or before it)."""
        if market.regimes.empty:
            return None
        rows = market.regimes.loc[:day]
        return rows[column].iloc[-1] if len(rows) else None

    def _probability(self, rs: list[float]) -> dict[str, Any]:
        a, limits = self._settings.risk.analysis, self._settings.risk.limits
        result = stats.bootstrap(
            rs,
            a.bootstrap_horizon_trades,
            a.bootstrap_paths,
            limits.risk_per_trade_pct,
            a.drawdown_alert_pct,
            a.losing_streak,
            a.min_trades_for_probability,
            a.bootstrap_seed,
        )
        if result is None:
            return {
                "available": False,
                "reason": f"only {len(rs)} past trades; at least {a.min_trades_for_probability} "
                "are needed before a probability has statistical support",
            }
        return {"available": True} | result.as_dict()

    def risk(self, db: Session, now: dt.datetime) -> dict[str, Any]:
        built = self.build(db, now)
        a, limits, plan = (
            self._settings.risk.analysis,
            self._settings.risk.limits,
            self._settings.risk.plan,
        )
        risk_pct = limits.risk_per_trade_pct
        baseline = next(s for s in self._catalogue() if s.baseline)
        markets: list[dict[str, Any]] = []
        for code, market in built.items():
            trades = market.trades[baseline.key]
            closed = sorted((t for t in trades if t.closed), key=lambda t: str(t.exit_date))
            rs = [float(t.r_multiple) for t in closed if t.r_multiple is not None]
            summary = stats.summarise(trades, risk_pct)

            def group(label_of: Any, closed: list[Trade] = closed) -> list[dict[str, Any]]:
                buckets: dict[str, list[Trade]] = {}
                for trade in closed:
                    buckets.setdefault(str(label_of(trade)), []).append(trade)
                return [
                    {"name": name, **stats.summarise(items, risk_pct).as_dict()}
                    for name, items in sorted(buckets.items())
                ]

            vol_rank = (
                regime.volatility_bucket(market.regimes["volatility_percentile"])
                if not market.regimes.empty
                else None
            )

            def vol_of(trade: Trade, vol_rank: Any = vol_rank) -> str:
                if vol_rank is None:
                    return "Unknown"
                rows = vol_rank.loc[: trade.signal_date]
                return str(rows.iloc[-1]) if len(rows) else "Unknown"

            midpoint = closed[len(closed) // 2].exit_date if closed else None
            stress = a.stress
            stop_slip_r = stress.stop_slippage_atr / plan.stop_atr_multiple
            cases = [
                ("As tested", rs),
                (
                    f"Costs {stress.extra_cost_bps_per_side:g} bps higher per side",
                    stats.stressed_r(closed, stress.extra_cost_bps_per_side, 0.0),
                ),
                (
                    f"Every stop fills {stress.stop_slippage_atr:g} ATR worse",
                    stats.stressed_r(closed, 0.0, stop_slip_r),
                ),
                (
                    "Both together",
                    stats.stressed_r(closed, stress.extra_cost_bps_per_side, stop_slip_r),
                ),
            ]
            stress_rows = []
            for name, values in cases:
                curve = stats.equity_curve(values, risk_pct)
                stress_rows.append(
                    {
                        "name": name,
                        "expectancy_r": sum(values) / len(values) if values else None,
                        "win_rate": sum(v > 0 for v in values) / len(values) if values else None,
                        "total_return_pct": (curve[-1] - 1) * 100.0,
                        "max_drawdown_pct": stats.max_drawdown_pct(curve),
                    }
                )

            max_positions = math.floor(limits.max_open_risk_pct / risk_pct)
            findings = self._findings(summary, group(vol_of), stress_rows)
            dates = [
                d
                for item in market.symbols.values()
                for d in (item.frame.index[0], item.frame.index[-1])
            ]
            markets.append(
                {
                    "code": code,
                    "name": market.config.name,
                    "currency": market.config.currency,
                    "period": {
                        "from": _day(min(dates)) if dates else None,
                        "to": _day(max(dates)) if dates else None,
                    },
                    "symbols_tested": len(market.symbols),
                    "summary": summary.as_dict(),
                    "probability": self._probability(rs),
                    "by_volatility": group(vol_of),
                    "by_regime": group(
                        lambda t, market=market: (
                            self._lookup(market, "regime", t.signal_date) or "Unknown"
                        )
                    ),
                    "by_period": group(
                        lambda t, midpoint=midpoint: (
                            "First half of the trades"
                            if midpoint is not None and str(t.exit_date) < str(midpoint)
                            else "Second half of the trades"
                        )
                    ),
                    "stress": stress_rows,
                    "loss_limits": {
                        "risk_per_trade_pct": risk_pct,
                        "max_open_risk_pct": limits.max_open_risk_pct,
                        "max_simultaneous_trades_at_full_risk": max_positions,
                        "planned_loss_per_trade_pct": risk_pct,
                        "worst_tested_trade_r": summary.worst_r,
                        "worst_tested_trade_pct_of_equity": (
                            summary.worst_r * risk_pct if summary.worst_r is not None else None
                        ),
                        "hypothetical_gap_r": stress.gap_r_multiple,
                        "all_open_trades_gap_pct_of_equity": -max_positions
                        * risk_pct
                        * stress.gap_r_multiple,
                    },
                    "findings": findings,
                    "portfolio": self._portfolio(trades)[0],
                    "equity_curve": self._portfolio(trades)[1],
                    "open_trades": [self._trade_json(t) for t in trades if not t.closed],
                }
            )
        return {
            "generated_at_utc": iso_utc(now),
            "label": LABEL,
            "strategy": {"name": baseline.name, "rule": baseline.rule},
            "execution": self._execution_note(),
            "warnings": [
                "BACKTEST: these numbers describe what the rules would have done on past "
                "data. They do not predict future results.",
                "Survivorship bias: the stock lists are today's large companies, which "
                "overstates past results.",
                "The score weights are the spec's untested starting values; nothing was "
                "fitted, so there is no separate out-of-sample period. First-half and "
                "second-half results are shown instead.",
                "Probabilities come from resampling past trades and assume future trades "
                "resemble them and are independent. Real losses tend to cluster.",
                "Costs are estimates. Earnings dates were not available, so trades were "
                "not filtered for event risk.",
            ],
            "markets": markets,
        }

    @staticmethod
    def _findings(
        summary: stats.Summary, by_vol: list[dict[str, Any]], stress: list[dict[str, Any]]
    ) -> list[str]:
        """Plain statements read straight off the tested numbers."""
        out: list[str] = []
        if summary.trades == 0:
            return ["The strategy made no completed trades in the stored history."]
        if summary.expectancy_r is not None:
            if abs(summary.expectancy_r) < 0.02:
                verdict = "roughly break-even"
            else:
                verdict = "positive" if summary.expectancy_r > 0 else "negative"
            out.append(
                f"Average result per trade was {summary.expectancy_r:+.2f} R ({verdict}) over "
                f"{summary.trades} trades."
            )
        scored = [b for b in by_vol if b["trades"] >= 5 and b["expectancy_r"] is not None]
        if len(scored) >= 2:
            worst = min(scored, key=lambda b: b["expectancy_r"])
            best = max(scored, key=lambda b: b["expectancy_r"])
            out.append(
                f"By volatility at entry it did worst in '{worst['name']}' "
                f"({worst['expectancy_r']:+.2f} R over {worst['trades']} trades) and best in "
                f"'{best['name']}' ({best['expectancy_r']:+.2f} R over {best['trades']})."
            )
        if summary.gap_stops:
            out.append(
                f"{summary.gap_stops} stops were jumped by an overnight gap; the worst cost "
                f"{summary.worst_gap_r:.2f} R instead of the planned -1 R."
            )
        else:
            out.append(
                "No stop was jumped by an overnight gap in this history; that can still happen."
            )
        both = stress[-1]
        if both["expectancy_r"] is not None and summary.expectancy_r is not None:
            if summary.expectancy_r > 0 >= both["expectancy_r"]:
                out.append(
                    "With higher costs and worse stop fills together, the average result turns negative."
                )
            else:
                out.append(
                    f"With higher costs and worse stop fills together, the average result is "
                    f"{both['expectancy_r']:+.2f} R per trade."
                )
        out.append(f"The longest run of losing trades was {summary.longest_losing_streak}.")
        return out

    def _execution_note(self) -> dict[str, Any]:
        plan = self._settings.risk.plan
        return {
            "fills": "Signals are read at the close; orders fill at the next session's open.",
            "stop": f"{plan.stop_atr_multiple:g} x ATR 14 below the entry; a gap through the stop fills at the open.",
            "target": f"{plan.target_r_multiple:g} x the stop distance above the entry.",
            "time_exit": f"After {plan.max_holding_sessions} sessions.",
            "costs": {code: cost.model_dump() for code, cost in self._settings.risk.costs.items()},
            "risk_per_trade_pct": self._settings.risk.limits.risk_per_trade_pct,
            "r_definition": "R = the planned loss if the stop is hit. +2 R means twice that amount gained.",
        }

    def _portfolio(self, trades: list[Trade]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Results when the total open-risk limit is respected: at most
        max_open_risk / risk_per_trade positions at once."""
        limits = self._settings.risk.limits
        slots = math.floor(limits.max_open_risk_pct / limits.risk_per_trade_pct)
        taken, skipped = stats.apply_position_cap(trades, slots)
        closed = sorted((t for t in taken if t.closed), key=lambda t: str(t.exit_date))
        curve = stats.equity_curve(
            [float(t.r_multiple or 0.0) for t in closed], limits.risk_per_trade_pct
        )
        return (
            {
                "max_positions": slots,
                "trades_taken": len(closed),
                "signals_skipped": skipped,
                "total_return_pct": (curve[-1] - 1.0) * 100.0,
                "max_drawdown_pct": stats.max_drawdown_pct(curve),
                "note": f"At most {slots} positions at once ({limits.max_open_risk_pct:g}% total "
                f"open risk at {limits.risk_per_trade_pct:g}% each). When more signals arrive "
                "than there are free slots, they are taken in date then alphabetical order.",
            },
            self._curve(closed, limits.risk_per_trade_pct),
        )

    @staticmethod
    def _curve(closed: list[Trade], risk_pct: float) -> list[dict[str, Any]]:
        ordered = sorted(closed, key=lambda t: str(t.exit_date))
        curve = stats.equity_curve([float(t.r_multiple or 0.0) for t in ordered], risk_pct)
        # One point per exit date (the last trade closed that day).
        points: dict[str, float] = {}
        for trade, value in zip(ordered, curve[1:], strict=True):
            points[str(trade.exit_date)] = (value - 1.0) * 100.0
        return [{"date": day, "return_pct": value} for day, value in points.items()]

    # -- screen 3: strategy comparison ----------------------------------------------------

    def strategies(self, db: Session, now: dt.datetime) -> dict[str, Any]:
        built = self.build(db, now)
        risk_pct = self._settings.risk.limits.risk_per_trade_pct
        markets: list[dict[str, Any]] = []
        for code, market in built.items():
            rows: list[dict[str, Any]] = []
            for spec in self._catalogue():
                trades = market.trades[spec.key]
                closed = [t for t in trades if t.closed]
                rs = [
                    float(t.r_multiple)
                    for t in sorted(closed, key=lambda t: str(t.exit_date))
                    if t.r_multiple is not None
                ]
                signals_now: list[str] = []
                for symbol, item in market.symbols.items():
                    entries, _ = spec.build(item.frame)
                    fresh = (
                        freshness.classify(item.frame.index[-1], market.last_completed)
                        == freshness.FRESH
                    )
                    if fresh and bool(entries.fillna(False).iloc[-1]):
                        signals_now.append(symbol)
                rows.append(
                    {
                        "key": spec.key,
                        "name": spec.name,
                        "rule": spec.rule,
                        "is_current": spec.baseline,
                        "summary": stats.summarise(trades, risk_pct).as_dict(),
                        "probability": self._probability(rs),
                        "portfolio": self._portfolio(trades)[0],
                        "equity_curve": self._portfolio(trades)[1],
                        "signals_now": signals_now,
                        "in_trade_now": sorted(t.symbol for t in trades if not t.closed),
                    }
                )
            current = next(r for r in rows if r["is_current"])
            for row in rows:
                mine, base = row["summary"]["expectancy_r"], current["summary"]["expectancy_r"]
                row["expectancy_vs_current_r"] = (
                    mine - base
                    if mine is not None and base is not None and not row["is_current"]
                    else None
                )
            benchmark_return = None
            if not market.benchmark.empty and market.symbols:
                start = min(item.frame.index[0] for item in market.symbols.values())
                series = market.benchmark.adjusted["close"].loc[start:]
                if len(series) > 1:
                    benchmark_return = (
                        float(series.iloc[-1]) / float(series.iloc[0]) - 1.0
                    ) * 100.0
            dates = [
                d
                for item in market.symbols.values()
                for d in (item.frame.index[0], item.frame.index[-1])
            ]
            markets.append(
                {
                    "code": code,
                    "name": market.config.name,
                    "currency": market.config.currency,
                    "period": {
                        "from": _day(min(dates)) if dates else None,
                        "to": _day(max(dates)) if dates else None,
                    },
                    "symbols_tested": len(market.symbols),
                    "as_of": _day(market.last_completed),
                    "benchmark": {
                        "symbol": market.config.relative_strength_benchmark,
                        "buy_and_hold_return_pct": benchmark_return,
                        "note": "Fully invested in the index for the whole period. The strategies "
                        f"risk only {risk_pct:g}% of equity per trade, so the two are not like for like.",
                    },
                    "strategies": rows,
                }
            )
        return {
            "generated_at_utc": iso_utc(now),
            "label": LABEL,
            "execution": self._execution_note(),
            "warnings": [
                "BACKTEST: past results on past data. They do not predict future results.",
                "Every strategy uses the same stop, target, time limit, costs and next-open fills, "
                "so only the entry and exit rules differ.",
                "Survivorship bias: the stock lists are today's large companies.",
                "Comparing six strategies and picking the best one in hindsight overstates how "
                "good it is. Prefer large, consistent differences over small ones.",
            ],
            "markets": markets,
        }
