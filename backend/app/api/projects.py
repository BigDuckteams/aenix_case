"""Проекты и импорт (docs/08-api.md § 2, S3.2)."""

from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError
from sqlmodel import select

from app.api.common import ERROR_RESPONSES
from app.db.models import Project
from app.deps import ProjectDep, SessionDep, SettingsDep
from app.errors import bad_request, payload_too_large
from app.openapi import PROJECT_CREATE_BODY
from app.schemas.project import (
    ProjectCreated,
    ProjectCreateFiles,
    ProjectCreateSample,
    ProjectDetail,
    ProjectList,
    ProjectPatch,
    SampleList,
)
from app.services import importing
from app.services import projects as service

router = APIRouter(tags=["projects"], responses=ERROR_RESPONSES)

_BODY_LIMIT = importing.MAX_ARCHIVE_BYTES + 1024 * 1024  # архив + служебные поля формы


@router.get("/samples", summary="Встроенные примеры")
def list_samples(settings: SettingsDep) -> SampleList:
    return SampleList(samples=service.list_samples(settings))


async def _read_multipart(request: Request) -> tuple[str | None, list[tuple[str, bytes]]]:
    form = await request.form()
    name = form.get("name")
    uploads = [*form.getlist("files"), *form.getlist("files[]")]
    archive = form.get("archive")
    items: list[tuple[str, bytes]] = []
    if archive is not None and not isinstance(archive, str):
        if uploads:
            raise bad_request("передайте либо files[], либо archive, но не оба сразу")
        items = importing.read_zip(await archive.read())
        name = name or PurePosixPath(archive.filename or "").stem
    else:
        for upload in uploads:
            if isinstance(upload, str):
                raise bad_request("files[] должны быть файлами")
            items.append((upload.filename or "", await upload.read()))
    return (name if isinstance(name, str) else None), items


@router.post(
    "/projects",
    status_code=201,
    summary="Создать проект",
    description=(
        "Один из вариантов тела: `multipart/form-data` (`name`, `files[]` или `archive`), "
        "`application/json` с файлами либо с `sample_id`. Пути нормализуются (защита от zip-slip), "
        "принимаются только `.java` в UTF-8; файл ≤ 2 МБ, архив ≤ 10 МБ, файлов ≤ 200."
    ),
    openapi_extra={"requestBody": PROJECT_CREATE_BODY},
)
async def create_project(
    request: Request, session: SessionDep, settings: SettingsDep
) -> ProjectCreated:
    length = request.headers.get("content-length")
    if length is not None and length.isdigit() and int(length) > _BODY_LIMIT:
        raise payload_too_large("тело запроса слишком велико", size=int(length))
    content_type = request.headers.get("content-type", "")

    scenarios: list[dict[str, Any]] = []
    if content_type.startswith("multipart/form-data"):
        name, items = await _read_multipart(request)
        files = await run_in_threadpool(importing.collect, items)
        name = name or "Проект"
    else:
        try:
            raw = json.loads(await request.body())
        except (ValueError, UnicodeDecodeError) as exc:
            raise bad_request("тело запроса — не JSON") from exc
        try:
            if isinstance(raw, dict) and "sample_id" in raw:
                sample = ProjectCreateSample.model_validate(raw)
                files, scenarios = service.load_sample(settings, sample.sample_id)
                name = sample.name or sample.sample_id
            else:
                body = ProjectCreateFiles.model_validate(raw)
                files = await run_in_threadpool(
                    importing.collect,
                    [(f.path, f.content.encode("utf-8")) for f in body.files],
                )
                name = body.name
        except ValidationError as exc:
            raise bad_request(
                "неверное тело запроса", errors=[e["msg"] for e in exc.errors()]
            ) from exc

    def create() -> ProjectCreated:
        project = service.create_project(session, settings, name, files, scenarios)
        return service.created_response(session, project)

    return await run_in_threadpool(create)


@router.get("/projects", summary="Список проектов")
def list_projects(session: SessionDep) -> ProjectList:
    projects = session.exec(select(Project).order_by(Project.id)).all()  # type: ignore[arg-type]
    return ProjectList(projects=[service.summary(session, p) for p in projects])


@router.get("/projects/{project_id}", summary="Проект: HEAD, оригинал, настройки, статус gate")
def get_project(project: ProjectDep, session: SessionDep, settings: SettingsDep) -> ProjectDetail:
    return service.detail(session, settings, project)


@router.patch("/projects/{project_id}", summary="Имя, главный класс, настройки")
def patch_project(
    payload: ProjectPatch, project: ProjectDep, session: SessionDep, settings: SettingsDep
) -> ProjectDetail:
    service.patch(session, settings, project, payload)
    return service.detail(session, settings, project)


@router.delete(
    "/projects/{project_id}",
    status_code=204,
    response_class=Response,
    summary="Удалить проект",
)
def delete_project(project: ProjectDep, session: SessionDep) -> None:
    service.delete_project(session, project)
