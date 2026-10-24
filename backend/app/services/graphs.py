"""Графы версии для API: движок → схемы (S3.7)."""

from __future__ import annotations

import dataclasses
from typing import Any

from pydantic import BaseModel
from sqlmodel import Session

from app.db.models import Version
from app.errors import not_found
from app.schemas.common import SourceRange
from app.schemas.graph import FlowGraph, NodeDetails
from app.services import versions as versions_service
from engine.graph.ids import split_node_id
from engine.graph.model import ApiRange
from engine.java.project import JavaProject, get_project


def java_project(session: Session, version: Version) -> JavaProject:
    """Проект движка для версии; кеш по ``content_hash`` общий для всех запросов."""
    return get_project(versions_service.version_files(session, version.id or 0))


def to_schema[M: BaseModel](model: type[M], graph: Any, version: Version) -> M:
    data = dataclasses.asdict(graph)
    data["version_id"] = version.id or 0
    data["content_hash"] = version.content_hash
    return model.model_validate(data)


def api_range(span: ApiRange) -> SourceRange:
    return SourceRange.model_validate(dataclasses.asdict(span))


def find_member_in_file(project: JavaProject, file: str, key: str) -> str | None:
    """id члена по ключу (``run()``), по полному id или по ``Type.key`` в файле."""
    if file not in project.files:
        return None
    for member in project.symbols(file).all_members():
        if key in {member.key, member.id, f"{member.type_path}.{member.key}"}:
            return member.id
    return None


def flow_schema(project: JavaProject, version: Version, method_id: str) -> FlowGraph:
    graph = project.flow(method_id)
    if graph is None:
        raise not_found(f"метод {method_id} не найден", method_id=method_id)
    return to_schema(FlowGraph, graph, version)


def node_details(project: JavaProject, node_id: str) -> NodeDetails:
    member_id, path = split_node_id(node_id)
    if path:
        graph = project.flow(member_id)
        node = next((n for n in graph.nodes if n.id == node_id), None) if graph else None
        if node is None:
            raise not_found(f"узел {node_id} не найден", node_id=node_id)
        return NodeDetails(
            node_id=node.id,
            kind=node.kind,
            name=node.label,
            range=api_range(node.range),
            data=node.data,
            complexity=node.complexity,
            finding_ids=[b.ref for b in node.badges if b.kind == "defect" and b.ref],
            errors=node.errors,
        )
    member = project.member(member_id)
    if member is not None:
        file = project.file_of(member)
        span = ApiRange.of(
            file, project.parsed(file).lines.range(member.start_byte, member.end_byte)
        )
        return NodeDetails(
            node_id=member.id,
            kind=member.kind,
            name=member.key,
            range=api_range(span),
            data={
                "modifiers": list(member.modifiers),
                "type": member.type_text,
                "params": [{"type": p.type, "name": p.name} for p in member.params],
                "throws": list(member.throws),
                "role": member.role,
            },
        )
    for decl in project.types():
        if decl.id == node_id:
            file = node_id.split("#", 1)[0]
            span = ApiRange.of(
                file, project.parsed(file).lines.range(decl.start_byte, decl.end_byte)
            )
            return NodeDetails(
                node_id=decl.id,
                kind=decl.kind,
                name=decl.path,
                range=api_range(span),
                data={
                    "modifiers": list(decl.modifiers),
                    "type_params": list(decl.type_params),
                    "extends": list(decl.extends),
                    "implements": list(decl.implements),
                },
            )
    raise not_found(f"узел {node_id} не найден", node_id=node_id)
