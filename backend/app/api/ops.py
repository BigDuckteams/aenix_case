"""Операции над графом (docs/08-api.md § 5). Заглушки контракта (S1.1): реализация — этап S5."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.common import ERROR_RESPONSES
from app.errors import not_implemented
from app.schemas.ops import (
    ExpressionCheck,
    ExpressionResult,
    OpsRequest,
    OpsResult,
    OpsValidation,
    Palette,
)

router = APIRouter(tags=["ops"], responses=ERROR_RESPONSES)


@router.post(
    "/projects/{project_id}/ops",
    summary="Применить операции над графом",
    description=(
        "Пакет применяется атомарно: при ошибке любой операции ни одна не применяется. "
        "`409 VERSION_CONFLICT` — `base_version_id` не равен HEAD; "
        "`422 INVALID_FRAGMENT` — после правки код не разбирается."
    ),
)
def apply_ops(project_id: int, payload: OpsRequest) -> OpsResult:
    raise not_implemented("S5")


@router.post(
    "/projects/{project_id}/ops/validate",
    summary="Сухая проверка операций",
    description="Ничего не сохраняет: предпросмотр diff и ошибки для подсветки в форме.",
)
def validate_ops(project_id: int, payload: OpsRequest) -> OpsValidation:
    raise not_implemented("S5")


@router.get("/projects/{project_id}/palette", summary="Блоки палитры и их поля")
def get_palette(project_id: int) -> Palette:
    raise not_implemented("S5")


@router.post(
    "/projects/{project_id}/validate/expression",
    summary="Проверить выражение, тип или идентификатор",
)
def validate_expression(project_id: int, payload: ExpressionCheck) -> ExpressionResult:
    raise not_implemented("S5")
