"""SQLAlchemy engine and session handling."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import REPO_ROOT, get_settings


class Base(DeclarativeBase):
    pass


def _resolve_sqlite_url(url: str) -> str:
    """Make relative SQLite paths relative to the repo root and create the folder."""
    prefix = "sqlite:///"
    if not url.startswith(prefix) or url.startswith(prefix + ":memory:"):
        return url
    path = Path(url[len(prefix) :])
    if not path.is_absolute():
        path = REPO_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"{prefix}{path}"


def make_engine(url: str) -> Engine:
    return create_engine(
        _resolve_sqlite_url(url),
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    )


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = make_engine(get_settings().database.url)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _session_factory


def init_db() -> None:
    from app import models  # noqa: F401  (registers tables)

    Base.metadata.create_all(get_engine())


def get_db() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
