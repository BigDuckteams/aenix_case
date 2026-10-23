"""Экспорт (docs/08-api.md § 10). Заглушки контракта (S1.1): реализация — этапы S3, S6 и S10."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Response

from app.api.common import ERROR_RESPONSES
from app.errors import not_implemented

router = APIRouter(tags=["export"], responses=ERROR_RESPONSES)


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
    project_id: int,
    version_id: int | None = None,
    format: Literal["zip", "file"] = "zip",
    path: str | None = None,
) -> Any:
    raise not_implemented("S3")


@router.get(
    "/projects/{project_id}/export/report",
    summary="Сводный отчёт",
    description="Анализ, преобразования и результаты тестов.",
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
    project_id: int, version_id: int | None = None, format: Literal["md", "json"] = "md"
) -> Any:
    raise not_implemented("S6")


@router.get(
    "/projects/{project_id}/export/bundle",
    summary="Комплект: исходники, отчёты, сценарии",
    description="Zip для комплекта сдачи; достаточен для воспроизведения бага.",
    response_class=Response,
    responses={
        200: {
            "description": "Архив",
            "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
def export_bundle(project_id: int, version_id: int | None = None) -> Any:
    raise not_implemented("S10")
