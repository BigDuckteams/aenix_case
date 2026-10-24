"""Демо-данные при первом старте (``JB_SEED_DEMO=1``, S3.9): проект из примера ``demo-orders``."""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from app.config import Settings
from app.db.models import Project
from app.services import projects as projects_service

log = logging.getLogger("app.seed")

DEMO_SAMPLE = "demo-orders"


def seed_demo(session: Session, settings: Settings) -> Project | None:
    """Создаёт демо-проект, если в БД ещё нет проектов. Повторный вызов ничего не делает."""
    if session.exec(select(Project.id)).first() is not None:
        return None
    try:
        files, scenarios = projects_service.load_sample(settings, DEMO_SAMPLE)
    except Exception:  # noqa: BLE001 - отсутствие примера не должно мешать старту сервера
        log.warning("demo sample %s is not available", DEMO_SAMPLE, exc_info=True)
        return None
    project = projects_service.create_project(session, settings, "Demo: заказы", files, scenarios)
    log.info("seeded demo project", extra={"project_id": project.id})
    return project
