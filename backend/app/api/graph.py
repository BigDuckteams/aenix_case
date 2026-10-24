"""Граф (docs/08-api.md § 4, S3.7): структура, блок-схема, дерево, узлы, позиция курсора."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.common import ERROR_RESPONSES
from app.deps import ProjectDep, SessionDep, SettingsDep
from app.errors import bad_request, not_found
from app.schemas.graph import (
    FlowGraph,
    LocateResult,
    NodeDetails,
    NodeLookup,
    ProjectTree,
    StructureGraph,
    StructureMode,
)
from app.services import analysis as analysis_service
from app.services import graphs
from app.services import versions as versions_service

router = APIRouter(tags=["graph"], responses=ERROR_RESPONSES)


@router.get("/projects/{project_id}/structure", summary="Граф структуры проекта")
def get_structure(
    project: ProjectDep,
    session: SessionDep,
    settings: SettingsDep,
    version_id: int | None = None,
    mode: StructureMode = "methods",
) -> StructureGraph:
    version = versions_service.resolve_version(session, project, version_id)
    java = graphs.java_project(session, version)
    model = graphs.to_schema(StructureGraph, java.structure(mode), version)
    return analysis_service.enrich_structure(model, java, project, settings)


@router.get("/projects/{project_id}/flow", summary="Блок-схема метода")
def get_flow(
    project: ProjectDep,
    session: SessionDep,
    settings: SettingsDep,
    method_id: str,
    version_id: int | None = None,
) -> FlowGraph:
    version = versions_service.resolve_version(session, project, version_id)
    java = graphs.java_project(session, version)
    model = graphs.flow_schema(java, version, method_id)
    return analysis_service.enrich_flow(model, java, project, settings)


@router.get(
    "/projects/{project_id}/tree",
    summary="Дерево «Проект»",
    description="Пакеты → файлы → типы → члены, с бейджами находок и сложностью.",
)
def get_tree(
    project: ProjectDep, session: SessionDep, settings: SettingsDep, version_id: int | None = None
) -> ProjectTree:
    version = versions_service.resolve_version(session, project, version_id)
    java = graphs.java_project(session, version)
    model = graphs.to_schema(ProjectTree, java.tree(), version)
    return analysis_service.enrich_tree(model, java, project, settings)


@router.post(
    "/projects/{project_id}/nodes/lookup",
    summary="Узел по id в теле запроса",
    description="Для длинных id, не помещающихся в путь.",
)
def lookup_node(project: ProjectDep, session: SessionDep, payload: NodeLookup) -> NodeDetails:
    version = versions_service.resolve_version(session, project, payload.version_id)
    return graphs.node_details(graphs.java_project(session, version), payload.node_id)


@router.get(
    "/projects/{project_id}/nodes/{node_id:path}",
    summary="Подробности узла",
    description="Поля (`data`), диапазон, оценка сложности, находки. `node_id` кодируется.",
)
def get_node(
    project: ProjectDep, session: SessionDep, node_id: str, version_id: int | None = None
) -> NodeDetails:
    version = versions_service.resolve_version(session, project, version_id)
    return graphs.node_details(graphs.java_project(session, version), node_id)


@router.get(
    "/projects/{project_id}/locate",
    summary="Позиция курсора → узел графа",
    description="Синхронизация редактора с графом (FR-05).",
)
def locate(
    project: ProjectDep,
    session: SessionDep,
    file: str,
    line: int,
    column: int,
    version_id: int | None = None,
) -> LocateResult:
    if line < 1 or column < 1:
        raise bad_request("line и column считаются с 1", line=line, column=column)
    version = versions_service.resolve_version(session, project, version_id)
    java = graphs.java_project(session, version)
    if file not in java.files:
        raise not_found(f"файл {file} не найден", path=file)
    found = java.locate(file, line, column)
    if found is None:
        return LocateResult()
    return LocateResult(node_id=found.node_id, method_id=found.method_id)
