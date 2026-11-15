"""Reads stored candles and assembles indicator results for the API.

All maths lives in app.core.indicators; this module only loads data and labels results
with the candle date, fetch time and source they were computed from.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import Any

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core import freshness, indicators
from app.models import CorporateAction, DataQualityIssue, FetchStatus, PriceBar, SymbolProfile
from app.services.calendars import MarketCalendar, as_utc

INSUFFICIENT = "insufficient data"


def _num(value: Any) -> float | None:
    """NaN / inf / None -> None so JSON never carries a made-up number."""
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _iso_utc(moment: dt.datetime | None) -> str | None:
    return as_utc(moment).isoformat().replace("+00:00", "Z") if moment else None


@dataclass
class SymbolData:
    symbol: str
    market: str
    frame: pd.DataFrame  # index: date; raw o/h/l/c, adj_close, volume, fetched_at
    adjusted: pd.DataFrame  # index: date; adjusted open/high/low/close

    @property
    def empty(self) -> bool:
        return self.frame.empty


class AnalysisService:
    def __init__(self, settings: Settings, source: str) -> None:
        self._settings = settings
        self._source = source

    # -- loading -----------------------------------------------------------------------

    def load(self, db: Session, symbol: str, market: str) -> SymbolData:
        rows = db.execute(
            select(
                PriceBar.date,
                PriceBar.open,
                PriceBar.high,
                PriceBar.low,
                PriceBar.close,
                PriceBar.adj_close,
                PriceBar.volume,
                PriceBar.fetched_at,
            )
            .where(PriceBar.symbol == symbol, PriceBar.source == self._source)
            .order_by(PriceBar.date)
        ).all()
        columns = ["date", "open", "high", "low", "close", "adj_close", "volume", "fetched_at"]
        frame = pd.DataFrame([tuple(r) for r in rows], columns=columns).set_index("date")
        if frame.empty:
            return SymbolData(symbol, market, frame, pd.DataFrame())
        adjusted = indicators.adjust_ohlc(
            frame["open"], frame["high"], frame["low"], frame["close"], frame["adj_close"]
        )
        return SymbolData(symbol, market, frame, adjusted)

    def calendar(self, market: str) -> MarketCalendar:
        return MarketCalendar(market, self._settings.markets[market], self._settings.sessions)

    # -- shared labelling --------------------------------------------------------------

    def provenance(
        self, data: SymbolData, calendar: MarketCalendar, last_completed: dt.date | None
    ) -> dict[str, Any]:
        """Candle date, fetch time, source and freshness for whatever is shown."""
        market = self._settings.markets[data.market]
        base: dict[str, Any] = {
            "symbol": data.symbol,
            "market": data.market,
            "currency": market.currency,
            "timezone": market.timezone,
            "source": self._source,
            "source_label": self._settings.provider.label,
            "last_completed_session": last_completed.isoformat() if last_completed else None,
        }
        if data.empty:
            return base | {
                "candle_date": None,
                "as_of_local": None,
                "fetched_at_utc": None,
                "freshness": freshness.classify(None, last_completed),
                "sessions_stored": 0,
            }
        candle_date: dt.date = data.frame.index[-1]
        as_of = calendar.candle_as_of_local(candle_date)
        return base | {
            "candle_date": candle_date.isoformat(),
            "as_of_local": as_of.isoformat() if as_of else None,
            "fetched_at_utc": _iso_utc(data.frame["fetched_at"].iloc[-1]),
            "freshness": freshness.classify(candle_date, last_completed),
            "sessions_stored": int(len(data.frame)),
        }

    # -- indicator series and snapshot ------------------------------------------------

    def indicator_series(
        self, data: SymbolData, benchmark: SymbolData | None
    ) -> dict[str, pd.Series]:
        cfg = self._settings.indicators
        adj = data.adjusted
        close, high, low = adj["close"], adj["high"], adj["low"]
        series: dict[str, pd.Series] = {}
        for window in cfg.sma_windows:
            series[f"sma_{window}"] = indicators.sma(close, window)
        for window in cfg.ema_windows:
            series[f"ema_{window}"] = indicators.ema(close, window)
        series["rsi"] = indicators.rsi(close, cfg.rsi_period)
        macd = indicators.macd(close, cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)
        series["macd"] = macd["macd"]
        series["macd_signal"] = macd["signal"]
        series["macd_histogram"] = macd["histogram"]
        series["atr"] = indicators.atr(high, low, close, cfg.atr_period)
        series["atr_pct"] = series["atr"] / close * 100.0
        bands = indicators.bollinger(close, cfg.bollinger.window, cfg.bollinger.num_std)
        series["bb_middle"] = bands["middle"]
        series["bb_upper"] = bands["upper"]
        series["bb_lower"] = bands["lower"]
        series["relative_volume"] = indicators.relative_volume(
            data.frame["volume"], cfg.relative_volume_window
        )
        for window in cfg.return_windows:
            series[f"return_{window}"] = indicators.session_return(close, window)
        series["volatility"] = indicators.volatility(
            close, cfg.volatility_window, cfg.trading_days_per_year
        )
        series["drawdown"] = indicators.drawdown(close)
        if benchmark is not None and not benchmark.empty:
            series["relative_strength"] = indicators.relative_strength(
                close, benchmark.adjusted["close"], cfg.relative_strength_window
            )
        return series

    def snapshot(
        self, data: SymbolData, benchmark: SymbolData | None, benchmark_symbol: str | None
    ) -> tuple[dict[str, float | None], dict[str, str]]:
        """Latest value of every indicator, plus the reason for each unavailable one."""
        cfg = self._settings.indicators
        values: dict[str, float | None] = {}
        reasons: dict[str, str] = {}
        if data.empty:
            return values, reasons
        have = len(data.frame)
        series = self.indicator_series(data, benchmark)
        for name, column in series.items():
            values[name] = _num(column.iloc[-1])
            if values[name] is None:
                reasons[name] = f"{INSUFFICIENT} ({have} sessions stored)"

        close = float(data.adjusted["close"].iloc[-1])
        values["last_close"] = _num(data.frame["close"].iloc[-1])
        values["last_adj_close"] = _num(close)
        for window in cfg.sma_windows:
            average = values.get(f"sma_{window}")
            key = f"pct_vs_sma_{window}"
            values[key] = (close / average - 1.0) * 100.0 if average else None
            if values[key] is None:
                reasons[key] = f"{INSUFFICIENT} ({have} sessions stored, needs {window})"
        values["max_drawdown"] = _num(indicators.max_drawdown(data.adjusted["close"]))

        if "relative_strength" not in series:
            values["relative_strength"] = None
            if benchmark_symbol is None:
                reasons["relative_strength"] = "not applicable: this is the benchmark itself"
            else:
                reasons["relative_strength"] = f"unavailable: no stored data for {benchmark_symbol}"
        elif values["relative_strength"] is None and benchmark is not None:
            benchmark_last = benchmark.frame.index[-1]
            if benchmark_last != data.frame.index[-1]:
                reasons["relative_strength"] = (
                    f"unavailable: {benchmark_symbol} has no candle for "
                    f"{data.frame.index[-1]} (its latest is {benchmark_last})"
                )
        return values, reasons

    def levels(self, data: SymbolData) -> dict[str, list[dict[str, Any]]]:
        cfg = self._settings.indicators.support_resistance
        if data.empty:
            return {"support": [], "resistance": []}
        adj = data.adjusted
        support, resistance = indicators.support_resistance(
            adj["high"],
            adj["low"],
            adj["close"],
            cfg.pivot_window,
            cfg.lookback_sessions,
            cfg.max_levels,
        )
        dates = list(adj.index)

        def describe(pivot: indicators.Pivot) -> dict[str, Any]:
            return {
                "price": pivot.price,
                "kind": f"swing {pivot.kind}",
                "pivot_date": dates[pivot.position].isoformat(),
                "confirmed_date": dates[pivot.confirmed_position].isoformat(),
            }

        return {
            "support": [describe(p) for p in support],
            "resistance": [describe(p) for p in resistance],
        }

    # -- other stored facts -----------------------------------------------------------

    def profile(self, db: Session, symbol: str) -> dict[str, Any] | None:
        row = db.scalar(
            select(SymbolProfile).where(
                SymbolProfile.symbol == symbol, SymbolProfile.source == self._source
            )
        )
        if row is None:
            return None
        return {
            "name": row.name,
            "sector": row.sector,
            "industry": row.industry,
            "exchange": row.exchange,
            "currency": row.currency,
            "quote_type": row.quote_type,
            "source": row.source,
            "fetched_at_utc": _iso_utc(row.fetched_at),
        }

    def issues(self, db: Session, symbol: str) -> list[dict[str, Any]]:
        rows = db.scalars(
            select(DataQualityIssue)
            .where(DataQualityIssue.symbol == symbol, DataQualityIssue.source == self._source)
            .order_by(DataQualityIssue.date.desc())
        )
        return [
            {
                "kind": r.kind,
                "date": r.date.isoformat() if r.date else None,
                "detail": r.detail,
                "detected_at_utc": _iso_utc(r.detected_at),
            }
            for r in rows
        ]

    def issue_counts(self, db: Session) -> dict[str, int]:
        rows = db.execute(
            select(DataQualityIssue.symbol, func.count())
            .where(DataQualityIssue.source == self._source)
            .group_by(DataQualityIssue.symbol)
        ).all()
        return {r[0]: int(r[1]) for r in rows}

    def actions(self, db: Session, symbol: str) -> list[dict[str, Any]]:
        rows = db.scalars(
            select(CorporateAction)
            .where(CorporateAction.symbol == symbol, CorporateAction.source == self._source)
            .order_by(CorporateAction.date.desc())
        )
        return [{"date": r.date.isoformat(), "type": r.action_type, "value": r.value} for r in rows]

    def fetch_status(self, db: Session) -> dict[str, FetchStatus]:
        rows = db.scalars(select(FetchStatus).where(FetchStatus.source == self._source))
        return {r.symbol: r for r in rows}

    def stored_ranges(self, db: Session) -> dict[str, tuple[dt.date, dt.date, int]]:
        rows = db.execute(
            select(PriceBar.symbol, func.min(PriceBar.date), func.max(PriceBar.date), func.count())
            .where(PriceBar.source == self._source)
            .group_by(PriceBar.symbol)
        ).all()
        return {r[0]: (r[1], r[2], int(r[3])) for r in rows}


def series_to_json(series: pd.Series) -> list[float | None]:
    return [_num(v) for v in series.to_numpy()]


def iso_utc(moment: dt.datetime | None) -> str | None:
    return _iso_utc(moment)
