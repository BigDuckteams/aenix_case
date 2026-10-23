"""Анализ (docs/08-api.md § 6). Заглушки контракта (S1.1): реализация — этап S7."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.common import ERROR_RESPONSES
from app.errors import not_implemented
from app.schemas.analysis import (
    AnalysisResponse,
    Category,
    ComplexityResponse,
    Finding,
    FindingsResponse,
    MetricsResponse,
    Severity,
)
from app.schemas.verify import RunRef

router = APIRouter(tags=["analysis"], responses=ERROR_RESPONSES)


@router.get("/projects/{project_id}/analysis", summary="Полный результат анализа версии")
def get_analysis(project_id: int, version_id: int | None = None) -> AnalysisResponse:
    raise not_implemented("S7")


@router.get("/projects/{project_id}/findings", summary="Находки с фильтрами")
def list_findings(
    project_id: int,
    version_id: int | None = None,
    severity: Severity | None = None,
    category: Category | None = None,
    file: str | None = None,
    fixable: bool | None = None,
) -> FindingsResponse:
    raise not_implemented("S7")


@router.post(
    "/projects/{project_id}/findings/{finding_id:path}/verify",
    status_code=202,
    summary="Динамическая проверка находки",
    description="Запускает `kind=verify` (бенчмарк или трассировка); дальше — SSE запуска.",
)
def verify_finding(project_id: int, finding_id: str) -> RunRef:
    raise not_implemented("S7")


@router.get(
    "/projects/{project_id}/findings/{finding_id:path}",
    summary="Карточка находки",
    description="Объяснение, вклады в сложность, доказательства, исправление.",
)
def get_finding(project_id: int, finding_id: str, version_id: int | None = None) -> Finding:
    raise not_implemented("S7")


@router.get(
    "/projects/{project_id}/complexity",
    summary="Оценка сложности узла или фрагмента",
    description="Задаётся `node_id` либо `file` + `start_line` + `end_line`; ответ с цепочкой вкладов.",
)
def get_complexity(
    project_id: int,
    version_id: int | None = None,
    node_id: str | None = None,
    file: str | None = None,
    start_line: int | None = None,
    end_line: int | None = None,
) -> ComplexityResponse:
    raise not_implemented("S7")


@router.get("/projects/{project_id}/metrics", summary="Метрики версии")
def get_metrics(
    project_id: int, version_id: int | None = None, compare_to: int | None = None
) -> MetricsResponse:
    raise not_implemented("S7")
