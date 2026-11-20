"""Database tables. All timestamps are stored as naive UTC."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PriceBar(Base):
    """One completed daily candle. `close` is split-adjusted (as the provider reports it);
    `adj_close` is split- and dividend-adjusted. Indicators use the adjusted series."""

    __tablename__ = "price_bars"
    __table_args__ = (UniqueConstraint("symbol", "date", "source", name="uq_price_bar"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    market: Mapped[str] = mapped_column(String(8))
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    adj_close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32))
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime)


class CorporateAction(Base):
    __tablename__ = "corporate_actions"
    __table_args__ = (
        UniqueConstraint("symbol", "date", "action_type", "source", name="uq_corporate_action"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    market: Mapped[str] = mapped_column(String(8))
    date: Mapped[dt.date] = mapped_column(Date)
    action_type: Mapped[str] = mapped_column(String(16))  # "split" | "dividend"
    value: Mapped[float] = mapped_column(Float)  # split ratio or dividend per share
    source: Mapped[str] = mapped_column(String(32))
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime)


class SymbolProfile(Base):
    __tablename__ = "symbol_profiles"
    __table_args__ = (UniqueConstraint("symbol", "source", name="uq_symbol_profile"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    market: Mapped[str] = mapped_column(String(8))
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    quote_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(32))
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime)


class FetchStatus(Base):
    """Source availability per symbol: last attempt, success, error and row count."""

    __tablename__ = "fetch_status"
    __table_args__ = (UniqueConstraint("symbol", "source", name="uq_fetch_status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    market: Mapped[str] = mapped_column(String(8))
    source: Mapped[str] = mapped_column(String(32))
    last_attempt_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    last_success_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    last_error_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_rows_fetched: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)


class DataQualityIssue(Base):
    """Warnings found by validation. Replaced for a symbol on every successful ingest."""

    __tablename__ = "data_quality_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    source: Mapped[str] = mapped_column(String(32))
    date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    kind: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str] = mapped_column(Text)
    detected_at: Mapped[dt.datetime] = mapped_column(DateTime)


class LatestQuote(Base):
    """Latest delayed price per symbol. Replaced in place on every quote refresh.

    `price` and `market_time` stay at the last good quote when a refresh fails; the failure
    is kept in `last_error` with `last_error_at`.
    """

    __tablename__ = "latest_quotes"
    __table_args__ = (UniqueConstraint("symbol", "source", name="uq_latest_quote"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    market: Mapped[str] = mapped_column(String(8))
    source: Mapped[str] = mapped_column(String(32))
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    previous_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    market_time: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    warnings: Mapped[str | None] = mapped_column(Text, nullable=True)  # one per line
    last_error_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
