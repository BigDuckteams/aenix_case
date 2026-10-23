"""Граф (docs/08-api.md § 4). Заглушки контракта (S1.1): реализация — этап S3 (на движке S2)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.common import ERROR_RESPONSES
from app.errors import not_implemented
from app.schemas.graph import (
    FlowGraph,
    LocateResult,
    NodeDetails,
    NodeLookup,
    ProjectTree,
    StructureGraph,
    StructureMode,
)

router = APIRouter(tags=["graph"], responses=ERROR_RESPONSES)


@router.get("/projects/{project_id}/structure", summary="Граф структуры проекта")
def get_structure(
    project_id: int, version_id: int | None = None, mode: StructureMode = "methods"
) -> StructureGraph:
    raise not_implemented("S3")


@router.get("/projects/{project_id}/flow", summary="Блок-схема метода")
def get_flow(project_id: int, method_id: str, version_id: int | None = None) -> FlowGraph:
    raise not_implemented("S3")


@router.get(
    "/projects/{project_id}/tree",
    summary="Дерево «Проект»",
    description="Пакеты → файлы → типы → члены, с бейджами находок и сложностью.",
)
def get_tree(project_id: int, version_id: int | None = None) -> ProjectTree:
    raise not_implemented("S3")


@router.post(
    "/projects/{project_id}/nodes/lookup",
    summary="Узел по id в теле запроса",
    description="Для длинных id, не помещающихся в путь.",
)
def lookup_node(project_id: int, payload: NodeLookup) -> NodeDetails:
    raise not_implemented("S3")


@router.get(
    "/projects/{project_id}/nodes/{node_id:path}",
    summary="Подробности узла",
    description="Поля (`data`), диапазон, оценка сложности, находки. `node_id` кодируется.",
)
def get_node(project_id: int, node_id: str, version_id: int | None = None) -> NodeDetails:
    raise not_implemented("S3")


@router.get(
    "/projects/{project_id}/locate",
    summary="Позиция курсора → узел графа",
    description="Синхронизация редактора с графом (FR-05).",
)
def locate(
    project_id: int, file: str, line: int, column: int, version_id: int | None = None
) -> LocateResult:
    raise not_implemented("S3")
