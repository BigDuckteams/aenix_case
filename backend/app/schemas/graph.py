"""Графы: блок-схема метода и структура проекта (docs/04-code-graph-model.md § 3–4)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from app.schemas.common import ApiModel, SourceRange, SyntaxIssue

NodeKind = Literal[
    "method",
    "var_decl",
    "assign",
    "operation",
    "condition",
    "switch",
    "case",
    "loop_for",
    "loop_foreach",
    "loop_while",
    "try",
    "catch",
    "finally",
    "throw",
    "return",
    "break",
    "continue",
    "yield",
    "lambda",
    "local_type",
    "labeled",
    "assert",
    "sync",
    "code",
]
"""Виды блоков. ``block`` и ``call`` не входят: ``block`` раскрывается в содержимое, а ``call`` —
бейдж поверх ``operation``/``var_decl``/``assign`` (04 § 3.1)."""

EdgeKind = Literal[
    "next",
    "true",
    "false",
    "case",
    "body",
    "back",
    "break",
    "continue",
    "exception",
    "call",
    "return",
]

BadgeKind = Literal["output", "error_output", "input", "call", "exception", "defect"]


class Badge(ApiModel):
    kind: BadgeKind
    label: str
    ref: str | None = None  # id находки для defect, id вызываемого метода для call


class FlowNode(ApiModel):
    id: str
    kind: NodeKind
    label: str  # короткий заголовок: «Условие», «Цикл (for each)»
    code: str  # краткий текст оператора (усечён для отображения)
    range: SourceRange
    parent_id: str | None = None  # контейнер
    data: dict[str, Any] = {}  # поля по kind: условие, тип, имя, init/cond/update, метки case…
    badges: list[Badge] = []
    complexity: str | None = None  # «O(n²)» для циклов и вызовов
    errors: list[str] = []


class FlowEdge(ApiModel):
    id: str
    source: str
    target: str
    kind: EdgeKind
    label: str | None = None


class FlowGraph(ApiModel):
    method_id: str
    signature: str
    file: str
    nodes: list[FlowNode]
    edges: list[FlowEdge]
    entry: str
    exits: list[str]
    version_id: int
    content_hash: str


StructureNodeType = Literal["type", "member"]
StructureNodeKind = Literal[
    "class", "interface", "record", "enum", "field", "constructor", "method", "initializer"
]
StructureEdgeKind = Literal["extends", "implements", "contains", "calls", "uses"]
StructureMode = Literal["types", "methods", "deps"]


class StructureNode(ApiModel):
    id: str
    node_type: StructureNodeType
    kind: StructureNodeKind
    name: str
    signature: str | None = None  # для членов: имя и типы параметров
    modifiers: list[str] = []
    type_params: list[str] = []
    parent_id: str | None = None  # тип-владелец или внешний тип
    range: SourceRange
    lines: int = 0
    method_id: str | None = None  # id блок-схемы, если у члена она есть
    complexity: str | None = None
    findings_count: int = 0
    cluster: str | None = None  # кластер зависимостей (режим ``deps``)


class StructureEdge(ApiModel):
    id: str
    source: str
    target: str
    kind: StructureEdgeKind
    weight: int = 1  # для calls: число вызовов


class StructureGraph(ApiModel):
    mode: StructureMode
    nodes: list[StructureNode]
    edges: list[StructureEdge]
    version_id: int
    content_hash: str


TreeNodeKind = Literal["package", "file", "type", "member"]


class TreeBadges(ApiModel):
    high: int = 0
    medium: int = 0
    low: int = 0


class TreeNode(ApiModel):
    """Узел дерева «Проект»: пакеты → файлы → типы → члены."""

    id: str
    kind: TreeNodeKind
    name: str
    node_id: str | None = None  # id в графе (для типов и членов)
    method_id: str | None = None
    member_kind: StructureNodeKind | None = None
    range: SourceRange | None = None
    complexity: str | None = None
    findings: TreeBadges = TreeBadges()
    children: list[TreeNode] = []


class ProjectTree(ApiModel):
    version_id: int
    roots: list[TreeNode]


class NodeDetails(ApiModel):
    node_id: str
    kind: str
    name: str
    range: SourceRange
    data: dict[str, Any] = {}
    complexity: str | None = None
    finding_ids: list[str] = []
    errors: list[str] = []


class NodeLookup(BaseModel):
    """Тело ``POST /nodes/lookup`` для длинных id, не помещающихся в путь."""

    node_id: str
    version_id: int | None = None


class LocateResult(ApiModel):
    """Позиция курсора → узел графа (синхронизация код ↔ граф)."""

    node_id: str | None = None
    method_id: str | None = None


class ParseRequest(BaseModel):
    """Живой разбор без сохранения (``POST /parse``)."""

    file: str
    content: str
    method_key: str | None = None


class ParseResult(ApiModel):
    syntax_errors: list[SyntaxIssue]
    flow: FlowGraph | None = None


TreeNode.model_rebuild()
