from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlmodel import Session

from app import __version__
from app.config import Settings, get_settings
from app.db.session import get_session
from app.errors import ErrorResponse
from app.schemas.health import HealthResponse
from engine.runtime.jdk import MIN_JDK_MAJOR, detect_jdk

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={500: {"model": ErrorResponse}},
    summary="Состояние сервиса: версия, JDK, БД",
)
def health(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    problems: list[str] = []

    jdk = detect_jdk(settings.java_home)
    if jdk.javac is None:
        problems.append("javac не найден: проверьте PATH или JB_JAVA_HOME")
    elif not jdk.ok:
        problems.append(f"Нужен JDK {MIN_JDK_MAJOR}+, найден javac {jdk.javac}")

    try:
        session.exec(text("SELECT 1"))
        db = "ok"
    except Exception as exc:  # noqa: BLE001 - любой сбой БД показываем в health
        db = "error"
        problems.append(f"БД недоступна: {exc}")

    return HealthResponse(
        status="ok" if not problems else "degraded",
        version=__version__,
        javac=jdk.javac,
        java=jdk.java,
        db=db,
        problems=problems,
    )
