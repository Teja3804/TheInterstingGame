from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.config import Settings, load_settings

FIXTURES = Path(__file__).parent / "fixtures"
REPO_CONFIG = Path(__file__).resolve().parents[2] / "config"


def load_fixture(name: str) -> pd.DataFrame:
    frame = pd.read_csv(FIXTURES / name, comment="#", parse_dates=["date"])
    frame["date"] = frame["date"].dt.date
    return frame


@pytest.fixture(scope="session")
def settings() -> Settings:
    return load_settings(REPO_CONFIG)


@pytest.fixture(scope="session")
def daily() -> pd.DataFrame:
    return load_fixture("synthetic_daily.csv")


@pytest.fixture(scope="session")
def benchmark() -> pd.DataFrame:
    return load_fixture("synthetic_benchmark.csv")


@pytest.fixture(scope="session")
def split() -> pd.DataFrame:
    return load_fixture("synthetic_split.csv")


@pytest.fixture(scope="session")
def hand() -> pd.DataFrame:
    return load_fixture("hand_calculated.csv")
