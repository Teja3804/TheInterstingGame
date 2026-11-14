"""Shared FastAPI dependencies. Tests override these to inject fakes."""

from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.db import get_session_factory
from app.providers.base import MarketDataProvider
from app.providers.yfinance_provider import YFinanceProvider
from app.services.analysis import AnalysisService
from app.services.ingestion import IngestionService


def get_settings_dep() -> Settings:
    return get_settings()


@lru_cache(maxsize=1)
def get_provider() -> MarketDataProvider:
    """One provider instance per process so request pacing is shared across calls."""
    return YFinanceProvider(get_settings().provider)


def get_analysis() -> AnalysisService:
    settings = get_settings()
    return AnalysisService(settings, source=settings.provider.name)


def get_ingestion() -> IngestionService:
    return IngestionService(get_settings(), get_provider(), get_session_factory())
