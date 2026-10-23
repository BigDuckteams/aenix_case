"""Версии и файлы (docs/08-api.md § 3). Заглушки контракта (S1.1): реализация — этапы S3 и S5."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.common import ERROR_RESPONSES
from app.errors import not_implemented
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

router = APIRouter(tags=["versions"], responses=ERROR_RESPONSES)


@router.get("/projects/{project_id}/versions", summary="История версий")
def list_versions(project_id: int) -> VersionList:
    raise not_implemented("S3")


@router.get("/projects/{project_id}/versions/{version_id}", summary="Версия и её файлы")
def get_version(project_id: int, version_id: int) -> VersionDetail:
    raise not_implemented("S3")


@router.post(
    "/projects/{project_id}/versions/{version_id}/restore",
    summary="Сделать версию HEAD (создаётся версия revert)",
)
def restore_version(project_id: int, version_id: int) -> VersionChange:
    raise not_implemented("S3")


@router.post("/projects/{project_id}/undo", summary="HEAD → родитель")
def undo(project_id: int) -> VersionChange:
    raise not_implemented("S5")


@router.post("/projects/{project_id}/redo", summary="HEAD → потомок, если есть")
def redo(project_id: int) -> VersionChange:
    raise not_implemented("S5")


@router.get("/projects/{project_id}/files", summary="Файлы версии")
def list_files(project_id: int, version_id: int | None = None) -> FileList:
    raise not_implemented("S3")


@router.get("/projects/{project_id}/files/{path:path}", summary="Содержимое файла")
def get_file(project_id: int, path: str, version_id: int | None = None) -> FileContent:
    raise not_implemented("S3")


@router.put(
    "/projects/{project_id}/files/{path:path}",
    summary="Сохранить файл",
    description=(
        "Создаёт версию `code_edit`; подряд идущие правки схлопываются. "
        "`409 VERSION_CONFLICT`, если `base_version_id` не равен HEAD."
    ),
)
def save_file(project_id: int, path: str, payload: FileSave) -> VersionChange:
    raise not_implemented("S3")


@router.post("/projects/{project_id}/files", status_code=201, summary="Создать файл")
def create_file(project_id: int, payload: FileCreate) -> VersionChange:
    raise not_implemented("S3")


@router.delete("/projects/{project_id}/files/{path:path}", summary="Удалить файл (новая версия)")
def delete_file(project_id: int, path: str) -> VersionChange:
    raise not_implemented("S3")


@router.get(
    "/projects/{project_id}/diff",
    summary="Различия версий",
    description="По файлам: unified diff и тексты обеих сторон.",
)
def diff_versions(
    project_id: int,
    from_version: Annotated[int, Query(alias="from")],
    to: int,
) -> VersionDiff:
    raise not_implemented("S3")


@router.post(
    "/projects/{project_id}/parse",
    summary="Живой разбор без сохранения",
    description="Для обновления схемы по мере набора кода: ошибки синтаксиса и граф метода.",
)
def parse_live(project_id: int, payload: ParseRequest) -> ParseResult:
    raise not_implemented("S3")
