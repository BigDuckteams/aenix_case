"""Сценарии (docs/08-api.md § 8.1). Заглушки контракта (S1.1): реализация — этап S6."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.api.common import ERROR_RESPONSES
from app.errors import not_implemented
from app.schemas.verify import (
    InputSchema,
    RunRef,
    Scenario,
    ScenarioCreate,
    ScenarioExport,
    ScenarioImport,
    ScenarioImportResult,
    ScenarioList,
    ScenarioUpdate,
)

router = APIRouter(tags=["scenarios"], responses=ERROR_RESPONSES)


@router.get("/projects/{project_id}/scenarios", summary="Сценарии со статусом эталона")
def list_scenarios(project_id: int) -> ScenarioList:
    raise not_implemented("S6")


@router.post("/projects/{project_id}/scenarios", status_code=201, summary="Создать сценарий")
def create_scenario(project_id: int, payload: ScenarioCreate) -> Scenario:
    raise not_implemented("S6")


@router.post(
    "/projects/{project_id}/scenarios/import",
    summary="Импорт сценариев",
    description='Формат `{"scenarios": [...]}`; пары `*.in` + `*.out` frontend собирает в этот же формат.',
)
def import_scenarios(project_id: int, payload: ScenarioImport) -> ScenarioImportResult:
    raise not_implemented("S6")


@router.get("/projects/{project_id}/scenarios/export", summary="Экспорт всех сценариев в JSON")
def export_scenarios(project_id: int) -> ScenarioExport:
    raise not_implemented("S6")


@router.post(
    "/projects/{project_id}/scenarios/generate",
    status_code=202,
    summary="Сгенерировать сценарии",
    description="Запуск `kind=generate`; результат — сценарии с `source=generated`.",
)
def generate_scenarios(project_id: int, version_id: int | None = None) -> RunRef:
    raise not_implemented("S6")


@router.put(
    "/projects/{project_id}/scenarios/{scenario_id}",
    summary="Изменить сценарий (сбрасывает эталон)",
)
def update_scenario(project_id: int, scenario_id: int, payload: ScenarioUpdate) -> Scenario:
    raise not_implemented("S6")


@router.delete(
    "/projects/{project_id}/scenarios/{scenario_id}",
    status_code=204,
    response_class=Response,
    summary="Удалить сценарий",
)
def delete_scenario(project_id: int, scenario_id: int) -> None:
    raise not_implemented("S6")


@router.get(
    "/projects/{project_id}/input-schema",
    summary="Выведенная схема ввода",
    description="Для отладки и отображения: как генератор понял формат ввода программы.",
)
def get_input_schema(project_id: int, version_id: int | None = None) -> InputSchema:
    raise not_implemented("S6")
