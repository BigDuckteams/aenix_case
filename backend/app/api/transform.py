"""Преобразования (docs/08-api.md § 7). Заглушки контракта (S1.1): реализация — этапы S8 и S9."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.common import ERROR_RESPONSES
from app.errors import not_implemented
from app.schemas.transform import (
    ApplyResult,
    CandidateDecision,
    DecomposeEdit,
    DecomposePlan,
    DecomposePlanRequest,
    DecomposePreview,
    ExtractMethodApply,
    ExtractMethodPreview,
    ExtractMethodRequest,
    FixApply,
    FixList,
    FixPreview,
    FixPreviewRequest,
    OptimizeApply,
    OptimizePlan,
    OptimizePlanRequest,
)
from app.schemas.verify import RunRef

router = APIRouter(tags=["transform"], responses=ERROR_RESPONSES)

_APPLY_NOTE = (
    "Создаётся версия-кандидат и запускается gate (`syntax → compile → scenarios`). "
    "Зелёный gate делает кандидата HEAD; красный — отклоняет."
)


@router.get("/projects/{project_id}/fixes", summary="Доступные исправления версии")
def list_fixes(project_id: int, version_id: int | None = None) -> FixList:
    raise not_implemented("S8")


@router.post(
    "/projects/{project_id}/fixes/{finding_id:path}/preview",
    summary="Предпросмотр исправления",
    description="Diff, ожидаемый эффект и предусловия. `422 PRECONDITION_FAILED`, если не выполнены.",
)
def preview_fix(project_id: int, finding_id: str, payload: FixPreviewRequest) -> FixPreview:
    raise not_implemented("S8")


@router.post(
    "/projects/{project_id}/fixes/{finding_id:path}/apply",
    status_code=202,
    summary="Применить исправление",
    description=_APPLY_NOTE,
)
def apply_fix(project_id: int, finding_id: str, payload: FixApply) -> ApplyResult:
    raise not_implemented("S8")


@router.post("/projects/{project_id}/optimize/plan", summary="План пакетной оптимизации")
def plan_optimize(project_id: int, payload: OptimizePlanRequest) -> OptimizePlan:
    raise not_implemented("S8")


@router.post(
    "/projects/{project_id}/optimize/apply",
    status_code=202,
    summary="Применить шаги оптимизации по очереди",
    description="Прогресс шагов приходит в SSE запуска событиями `step`.",
)
def apply_optimize(project_id: int, payload: OptimizeApply) -> RunRef:
    raise not_implemented("S8")


@router.post(
    "/projects/{project_id}/extract-method/preview", summary="Предпросмотр выделения метода"
)
def preview_extract_method(project_id: int, payload: ExtractMethodRequest) -> ExtractMethodPreview:
    raise not_implemented("S9")


@router.post(
    "/projects/{project_id}/extract-method/apply",
    status_code=202,
    summary="Выделить метод",
    description=_APPLY_NOTE,
)
def apply_extract_method(project_id: int, payload: ExtractMethodApply) -> ApplyResult:
    raise not_implemented("S9")


@router.post("/projects/{project_id}/decompose/plan", summary="План декомпозиции монолита")
def plan_decompose(project_id: int, payload: DecomposePlanRequest) -> DecomposePlan:
    raise not_implemented("S9")


@router.post(
    "/projects/{project_id}/decompose/preview",
    summary="Предпросмотр декомпозиции по отредактированному плану",
)
def preview_decompose(project_id: int, payload: DecomposeEdit) -> DecomposePreview:
    raise not_implemented("S9")


@router.post(
    "/projects/{project_id}/decompose/apply",
    status_code=202,
    summary="Применить декомпозицию",
    description=_APPLY_NOTE,
)
def apply_decompose(project_id: int, payload: DecomposeEdit) -> ApplyResult:
    raise not_implemented("S9")


@router.post(
    "/projects/{project_id}/versions/{version_id}/accept",
    summary="Подтвердить кандидата после красного gate",
    description="Для `behavior_preserving = false`: обновляет эталоны затронутых сценариев.",
)
def accept_candidate(project_id: int, version_id: int) -> CandidateDecision:
    raise not_implemented("S8")


@router.post("/projects/{project_id}/versions/{version_id}/reject", summary="Отклонить кандидата")
def reject_candidate(project_id: int, version_id: int) -> CandidateDecision:
    raise not_implemented("S8")
