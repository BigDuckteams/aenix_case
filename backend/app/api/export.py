"""Экспорт (docs/08-api.md § 10). Исходники — S3; отчёт — S6; комплект сдачи — S10."""

from __future__ import annotations

import io
import zipfile
from typing import Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Response

from app.api.common import ERROR_RESPONSES
from app.deps import ProjectDep, SessionDep
from app.errors import bad_request, not_found
from app.services import importing, reports
from app.services import versions as versions_service

router = APIRouter(tags=["export"], responses=ERROR_RESPONSES)

_ZIP_TIME = (2020, 1, 1, 0, 0, 0)  # фиксированная дата: один и тот же архив для одной версии


def _attachment(filename: str) -> dict[str, str]:
    ascii_name = filename.encode("ascii", "replace").decode().replace("?", "_")
    return {
        "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    }


def zip_sources(files: dict[str, str]) -> bytes:
    """Архив ``src/<путь>`` в UTF-8 с LF: распаковывается в готовое дерево исходников."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            info = zipfile.ZipInfo(f"src/{path}", _ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[path].encode("utf-8"))
    return buffer.getvalue()


@router.get(
    "/projects/{project_id}/export/source",
    summary="Исходники версии",
    description="`format=zip` — архив (`src/…`), `format=file` — один файл по `path`.",
    response_class=Response,
    responses={
        200: {
            "description": "Архив или файл",
            "content": {
                "application/zip": {"schema": {"type": "string", "format": "binary"}},
                "text/x-java-source": {"schema": {"type": "string"}},
            },
        }
    },
)
def export_source(
    project: ProjectDep,
    session: SessionDep,
    version_id: int | None = None,
    format: Literal["zip", "file"] = "zip",
    path: str | None = None,
) -> Any:
    version = versions_service.resolve_version(session, project, version_id)
    files = versions_service.version_files(session, version.id or 0)
    if format == "file":
        if path is None:
            raise bad_request("для format=file нужен параметр path")
        clean = importing.normalize_path(path)
        if clean not in files:
            raise not_found(f"файл {clean} не найден", path=clean)
        return Response(
            files[clean].encode("utf-8"),
            media_type="text/x-java-source; charset=utf-8",
            headers=_attachment(clean.rsplit("/", 1)[-1]),
        )
    return Response(
        zip_sources(files),
        media_type="application/zip",
        headers=_attachment(f"project-{project.id}-v{version.number}.zip"),
    )


@router.get(
    "/projects/{project_id}/export/report",
    summary="Сводный отчёт",
    description="Версия, результаты последней проверки, сценарии и история запусков.",
    response_class=Response,
    responses={
        200: {
            "description": "Отчёт",
            "content": {
                "application/json": {"schema": {"type": "object"}},
                "text/markdown": {"schema": {"type": "string"}},
            },
        }
    },
)
def export_report(
    project: ProjectDep,
    session: SessionDep,
    version_id: int | None = None,
    format: Literal["md", "json"] = "md",
) -> Any:
    version = versions_service.resolve_version(session, project, version_id)
    body, media_type, filename = reports.project_report(session, project, version, format)
    return Response(body, media_type=media_type, headers=_attachment(filename))


@router.get(
    "/projects/{project_id}/export/bundle",
    summary="Комплект: исходники, отчёты, сценарии",
    description="Zip для комплекта сдачи; достаточен для воспроизведения проверки.",
    response_class=Response,
    responses={
        200: {
            "description": "Архив",
            "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
def export_bundle(project: ProjectDep, session: SessionDep, version_id: int | None = None) -> Any:
    version = versions_service.resolve_version(session, project, version_id)
    return Response(
        reports.bundle(session, project, version),
        media_type="application/zip",
        headers=_attachment(f"bundle-project-{project.id}-v{version.number}.zip"),
    )
