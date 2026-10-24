"""Зависимости FastAPI: сессия БД, настройки, менеджер запусков, проект и версия из пути."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Request
from sqlmodel import Session

from app.config import Settings, get_settings
from app.db.models import Project, Version
from app.db.session import get_session
from app.services import projects as projects_service
from app.services import versions as versions_service

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_run_manager(request: Request) -> Any:
    """``app.jobs.run_manager.RunManager``, созданный при старте приложения."""
    return request.app.state.run_manager


RunManagerDep = Annotated[Any, Depends(get_run_manager)]


def get_project(project_id: int, session: SessionDep) -> Project:
    return projects_service.get_or_404(session, project_id)


ProjectDep = Annotated[Project, Depends(get_project)]


def version_for(session: Session, project: Project, version_id: int | None) -> Version:
    return versions_service.resolve_version(session, project, version_id)
