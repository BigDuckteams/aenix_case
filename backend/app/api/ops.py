"""Операции над графом (docs/08-api.md § 5, S5): пакет → версия `graph_op`, сухая проверка, палитра."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.common import ERROR_RESPONSES
from app.deps import ProjectDep, SessionDep
from app.schemas.ops import (
    ExpressionCheck,
    ExpressionResult,
    OpsRequest,
    OpsResult,
    OpsValidation,
    Palette,
)
from app.services import ops as service

router = APIRouter(tags=["ops"], responses=ERROR_RESPONSES)


@router.post(
    "/projects/{project_id}/ops",
    summary="Применить операции над графом",
    description=(
        "Пакет применяется атомарно: при ошибке любой операции ни одна не применяется. "
        "`409 VERSION_CONFLICT` — `base_version_id` не равен HEAD; "
        "`422 INVALID_FRAGMENT` — после правки код не разбирается. Идентификаторы в каждой "
        "следующей операции пакета относятся к состоянию после предыдущих."
    ),
)
def apply_ops(project: ProjectDep, session: SessionDep, payload: OpsRequest) -> OpsResult:
    return service.apply(session, project, payload)


@router.post(
    "/projects/{project_id}/ops/validate",
    summary="Сухая проверка операций",
    description="Ничего не сохраняет: предпросмотр diff и ошибки для подсветки в форме.",
)
def validate_ops(project: ProjectDep, session: SessionDep, payload: OpsRequest) -> OpsValidation:
    return service.validate(session, project, payload)


@router.get("/projects/{project_id}/palette", summary="Блоки палитры и их поля")
def get_palette(project: ProjectDep) -> Palette:
    del project
    return service.palette()


@router.post(
    "/projects/{project_id}/validate/expression",
    summary="Проверить выражение, тип или идентификатор",
)
def validate_expression(
    project: ProjectDep, session: SessionDep, payload: ExpressionCheck
) -> ExpressionResult:
    return service.check_expression(session, project, payload)
