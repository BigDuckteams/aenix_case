"""Версии и файлы (docs/08-api.md § 3, S3.3). Правка графа и undo/redo по операциям — S5."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.common import ERROR_RESPONSES
from app.deps import ProjectDep, SessionDep
from app.errors import bad_request, not_found, payload_too_large
from app.schemas.graph import ParseRequest, ParseResult
from app.schemas.project import (
    FileContent,
    FileCreate,
    FileList,
    FileSave,
    VersionChange,
    VersionDetail,
    VersionDiff,
    VersionList,
)
from app.services import graphs, importing
from app.services import versions as service
from engine.java.project import get_project

router = APIRouter(tags=["versions"], responses=ERROR_RESPONSES)


def _checked_path(path: str, *, new: bool = False) -> str:
    clean = importing.normalize_path(path)
    if new and not clean.endswith(".java"):
        raise bad_request(f"принимаются только .java: {clean}", path=clean)
    return clean


def _checked_content(path: str, content: str) -> str:
    if len(content.encode("utf-8")) > importing.MAX_FILE_BYTES:
        raise payload_too_large(f"файл {path} больше 2 МБ", path=path)
    return content


@router.get("/projects/{project_id}/versions", summary="История версий")
def list_versions(project: ProjectDep, session: SessionDep) -> VersionList:
    head = service.head_version(session, project)
    return VersionList(
        head_version_id=head.id or 0,
        versions=[service.version_info(v) for v in service.list_versions(session, project)],
    )


@router.get("/projects/{project_id}/versions/{version_id}", summary="Версия и её файлы")
def get_version(project: ProjectDep, session: SessionDep, version_id: int) -> VersionDetail:
    version = service.get_version(session, project, version_id)
    files = service.version_files(session, version.id or 0)
    return VersionDetail(version=service.version_info(version), files=service.file_entries(files))


@router.post(
    "/projects/{project_id}/versions/{version_id}/restore",
    summary="Сделать версию HEAD (создаётся версия revert)",
)
def restore_version(project: ProjectDep, session: SessionDep, version_id: int) -> VersionChange:
    return service.restore(session, project, version_id)


@router.post("/projects/{project_id}/undo", summary="HEAD → родитель")
def undo(project: ProjectDep, session: SessionDep) -> VersionChange:
    return service.undo(session, project)


@router.post("/projects/{project_id}/redo", summary="HEAD → потомок, если есть")
def redo(project: ProjectDep, session: SessionDep) -> VersionChange:
    return service.redo(session, project)


@router.get("/projects/{project_id}/files", summary="Файлы версии")
def list_files(project: ProjectDep, session: SessionDep, version_id: int | None = None) -> FileList:
    version = service.resolve_version(session, project, version_id)
    files = service.version_files(session, version.id or 0)
    return FileList(version_id=version.id or 0, files=service.file_entries(files))


@router.get("/projects/{project_id}/files/{path:path}", summary="Содержимое файла")
def get_file(
    project: ProjectDep, session: SessionDep, path: str, version_id: int | None = None
) -> FileContent:
    clean = _checked_path(path)
    version = service.resolve_version(session, project, version_id)
    files = service.version_files(session, version.id or 0)
    if clean not in files:
        raise not_found(f"файл {clean} не найден", path=clean)
    return FileContent(
        path=clean,
        version_id=version.id or 0,
        content=files[clean],
        syntax_errors=service.syntax_issues(get_project(files), {clean}),
    )


@router.put(
    "/projects/{project_id}/files/{path:path}",
    summary="Сохранить файл",
    description=(
        "Создаёт версию `code_edit`; подряд идущие правки схлопываются в HEAD. "
        "`409 VERSION_CONFLICT`, если `base_version_id` не равен HEAD."
    ),
)
def save_file(
    project: ProjectDep, session: SessionDep, path: str, payload: FileSave
) -> VersionChange:
    clean = _checked_path(path)
    return service.save_file(
        session, project, clean, _checked_content(clean, payload.content), payload.base_version_id
    )


@router.post("/projects/{project_id}/files", status_code=201, summary="Создать файл")
def create_file(project: ProjectDep, session: SessionDep, payload: FileCreate) -> VersionChange:
    clean = _checked_path(payload.path, new=True)
    return service.create_file(session, project, clean, _checked_content(clean, payload.content))


@router.delete("/projects/{project_id}/files/{path:path}", summary="Удалить файл (новая версия)")
def delete_file(project: ProjectDep, session: SessionDep, path: str) -> VersionChange:
    return service.delete_file(session, project, _checked_path(path))


@router.get(
    "/projects/{project_id}/diff",
    summary="Различия версий",
    description="По файлам: unified diff и тексты обеих сторон.",
)
def diff_versions(
    project: ProjectDep,
    session: SessionDep,
    from_version: Annotated[int, Query(alias="from")],
    to: int,
) -> VersionDiff:
    old = service.get_version(session, project, from_version)
    new = service.get_version(session, project, to)
    return VersionDiff(
        from_version_id=old.id or 0,
        to_version_id=new.id or 0,
        files=service.diff_files(
            service.version_files(session, old.id or 0), service.version_files(session, new.id or 0)
        ),
    )


@router.post(
    "/projects/{project_id}/parse",
    summary="Живой разбор без сохранения",
    description="Для обновления схемы по мере набора кода: ошибки синтаксиса и граф метода.",
)
def parse_live(project: ProjectDep, session: SessionDep, payload: ParseRequest) -> ParseResult:
    path = _checked_path(payload.file)
    head = service.head_version(session, project)
    files = service.version_files(session, head.id or 0)
    files[path] = _checked_content(path, payload.content)
    java = get_project(files)
    flow = None
    if payload.method_key:
        member_id = graphs.find_member_in_file(java, path, payload.method_key)
        if member_id is not None:
            flow = graphs.flow_schema(java, head, member_id)
    return ParseResult(syntax_errors=service.syntax_issues(java, {path}), flow=flow)
