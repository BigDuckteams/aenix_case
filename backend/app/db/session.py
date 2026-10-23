"""Движок SQLite, режим WAL и сессии."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.config import Settings, get_settings
from app.db import models  # noqa: F401  (регистрирует таблицы в metadata)

_engine: Engine | None = None


def make_engine(settings: Settings) -> Engine:
    settings.ensure_dirs()
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn: Any, _: Any) -> None:  # pragma: no cover - вызывается драйвером
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

    return engine


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = make_engine(get_settings())
    return _engine


def set_engine(engine: Engine | None) -> None:
    """Подмена движка (тесты) или сброс."""
    global _engine
    _engine = engine


def init_db(engine: Engine | None = None) -> None:
    SQLModel.metadata.create_all(engine or get_engine())


def get_session() -> Iterator[Session]:
    """Зависимость FastAPI: sync-сессия на запрос."""
    with Session(get_engine()) as session:
        yield session
