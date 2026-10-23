"""Модели графов engine (docs/04-code-graph-model.md § 3–4).

Поля совпадают с Pydantic-схемами API (`app.schemas.graph`): `app` превращает эти dataclass'ы
в ответы через `Model.model_validate(dataclasses.asdict(graph))`, а тест следит, чтобы наборы
полей не разошлись. `engine` не импортирует `app`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.graph.ranges import SourceRange as ByteRange


@dataclass(frozen=True, slots=True)
class ApiRange:
    """Диапазон кода в координатах API: строки с 1, колонки в UTF-16 с 1 (ADR-11)."""

    file: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int

    @staticmethod
    def of(file: str, r: ByteRange) -> ApiRange:
        return ApiRange(file, r.start.line, r.start.column, r.end.line, r.end.column)

    def contains(self, line: int, col: int) -> bool:
        return (self.start_line, self.start_col) <= (line, col) < (self.end_line, self.end_col)

    @property
    def size(self) -> tuple[int, int]:
        """Мера «размера» для выбора самого глубокого узла: строки, затем колонки."""
        return (self.end_line - self.start_line, self.end_col - self.start_col)


@dataclass(frozen=True, slots=True)
class Badge:
    kind: str  # output | error_output | input | call | exception | defect
    label: str
    ref: str | None = None


@dataclass(slots=True)
class FlowNode:
    id: str
    kind: str
    label: str
    code: str
    range: ApiRange
    parent_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    badges: list[Badge] = field(default_factory=list)
    complexity: str | None = None
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FlowEdge:
    id: str
    source: str
    target: str
    kind: str
    label: str | None = None


@dataclass(slots=True)
class FlowGraph:
    method_id: str
    signature: str
    file: str
    nodes: list[FlowNode]
    edges: list[FlowEdge]
    entry: str
    exits: list[str]
    version_id: int = 0
    content_hash: str = ""


@dataclass(slots=True)
class StructureNode:
    id: str
    node_type: str  # type | member
    kind: str
    name: str
    range: ApiRange
    signature: str | None = None
    modifiers: list[str] = field(default_factory=list)
    type_params: list[str] = field(default_factory=list)
    parent_id: str | None = None
    lines: int = 0
    method_id: str | None = None
    complexity: str | None = None
    findings_count: int = 0
    cluster: str | None = None


@dataclass(slots=True)
class StructureEdge:
    id: str
    source: str
    target: str
    kind: str  # extends | implements | contains | calls | uses
    weight: int = 1


@dataclass(slots=True)
class StructureGraph:
    mode: str
    nodes: list[StructureNode]
    edges: list[StructureEdge]
    version_id: int = 0
    content_hash: str = ""


@dataclass(slots=True)
class TreeBadges:
    high: int = 0
    medium: int = 0
    low: int = 0


@dataclass(slots=True)
class TreeNode:
    id: str
    kind: str  # package | file | type | member
    name: str
    node_id: str | None = None
    method_id: str | None = None
    member_kind: str | None = None
    range: ApiRange | None = None
    complexity: str | None = None
    findings: TreeBadges = field(default_factory=TreeBadges)
    children: list[TreeNode] = field(default_factory=list)


@dataclass(slots=True)
class ProjectTree:
    version_id: int
    roots: list[TreeNode]
