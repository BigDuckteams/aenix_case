from __future__ import annotations

import os
import tempfile

# Каталог данных тестов задаём до импорта приложения: Settings читает окружение при первом обращении.
os.environ.setdefault("JB_DATA_DIR", tempfile.mkdtemp(prefix="jb-test-"))
os.environ.setdefault("JB_LOG_LEVEL", "WARNING")

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.config import Settings  # noqa: E402
from app.db.session import init_db, make_engine, set_engine  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def engine(tmp_path) -> Iterator[Engine]:
    """Чистая SQLite-БД на тест."""
    eng = make_engine(Settings(data_dir=tmp_path))
    init_db(eng)
    set_engine(eng)
    yield eng
    set_engine(None)
    eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c
