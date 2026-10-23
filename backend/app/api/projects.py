"""Проекты и импорт (docs/08-api.md § 2). Заглушки контракта (S1.1): реализация — этап S3."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.api.common import ERROR_RESPONSES
from app.errors import not_implemented
from app.schemas.project import (
    PROJECT_CREATE_MULTIPART,
    ProjectCreated,
    ProjectCreateJson,
    ProjectDetail,
    ProjectList,
    ProjectPatch,
    SampleList,
)

router = APIRouter(tags=["projects"], responses=ERROR_RESPONSES)


@router.get("/samples", summary="Встроенные примеры")
def list_samples() -> SampleList:
    raise not_implemented("S3")


@router.post(
    "/projects",
    status_code=201,
    summary="Создать проект",
    description=(
        "Один из вариантов тела: `multipart/form-data` (`name`, `files[]` или `archive`), "
        "`application/json` с файлами либо с `sample_id`. Пути нормализуются (защита от zip-slip), "
        "принимаются только `.java` в UTF-8."
    ),
    openapi_extra={
        "requestBody": {
            "content": {"multipart/form-data": {"schema": PROJECT_CREATE_MULTIPART}},
        }
    },
)
def create_project(payload: ProjectCreateJson) -> ProjectCreated:
    raise not_implemented("S3")


@router.get("/projects", summary="Список проектов")
def list_projects() -> ProjectList:
    raise not_implemented("S3")


@router.get("/projects/{project_id}", summary="Проект: HEAD, оригинал, настройки, статус gate")
def get_project(project_id: int) -> ProjectDetail:
    raise not_implemented("S3")


@router.patch("/projects/{project_id}", summary="Имя, главный класс, настройки")
def patch_project(project_id: int, payload: ProjectPatch) -> ProjectDetail:
    raise not_implemented("S3")


@router.delete(
    "/projects/{project_id}",
    status_code=204,
    response_class=Response,
    summary="Удалить проект",
)
def delete_project(project_id: int) -> None:
    raise not_implemented("S3")
