"""Граф структуры проекта и дерево «Проект» (S2.8, docs/04 § 4).

Узлы — типы (``class``/``interface``/``record``/``enum``) и их члены (поле, конструктор, метод,
инициализатор). Рёбра: ``contains``, ``extends``, ``implements``, ``calls`` (вес — число вызовов)
и ``uses`` (метод → поле или тип). Режим ``types`` оставляет только типы и наследование,
``methods`` и ``deps`` — всё; кластеры ``deps`` проставляет декомпозиция (S9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.graph.model import (
    ApiRange,
    ProjectTree,
    StructureEdge,
    StructureGraph,
    StructureNode,
    TreeBadges,
    TreeNode,
)
from engine.java.symbols import Member, TypeDecl

if TYPE_CHECKING:
    from engine.java.project import JavaProject

MODES = ("types", "methods", "deps")


def _range(project: JavaProject, file: str, start: int, end: int) -> ApiRange:
    return ApiRange.of(file, project.parsed(file).lines.range(start, end))


def _member_node(project: JavaProject, member: Member, owner: TypeDecl) -> StructureNode:
    file = project.file_of(member)
    span = _range(project, file, member.start_byte, member.end_byte)
    flowable = member.kind in {"method", "constructor", "initializer"}
    modifiers = list(member.modifiers)
    if member.role == "constant":
        modifiers.append("enum constant")
    elif member.role == "component":
        modifiers.append("record component")
    return StructureNode(
        id=member.id,
        node_type="member",
        kind=member.kind,
        name=member.name,
        range=span,
        signature=member.key,
        modifiers=modifiers,
        type_params=list(member.type_params),
        parent_id=owner.id,
        lines=span.end_line - span.start_line + 1,
        method_id=member.id if flowable else None,
    )


def build_structure(project: JavaProject, mode: str = "methods") -> StructureGraph:
    if mode not in MODES:
        raise ValueError(f"неизвестный режим графа: {mode}")
    nodes: list[StructureNode] = []
    edges: list[StructureEdge] = []
    seen: set[str] = set()

    def add_edge(source: str, target: str, kind: str, weight: int = 1) -> None:
        edge_id = f"{kind}:{source}->{target}"
        if edge_id not in seen:
            seen.add(edge_id)
            edges.append(StructureEdge(edge_id, source, target, kind, weight))

    table = project.table
    for path in project.files:
        for decl in project.symbols(path).all_types():
            span = _range(project, path, decl.start_byte, decl.end_byte)
            outer = table.outer(decl)
            nodes.append(
                StructureNode(
                    id=decl.id,
                    node_type="type",
                    kind=decl.kind if decl.kind != "annotation" else "interface",
                    name=decl.name,
                    range=span,
                    modifiers=list(decl.modifiers),
                    type_params=list(decl.type_params),
                    parent_id=outer.id if outer is not None else None,
                    lines=span.end_line - span.start_line + 1,
                )
            )
            if outer is not None:
                add_edge(outer.id, decl.id, "contains")
            for text in decl.extends:
                parent = table.type_named(text, decl)
                if parent is not None:
                    add_edge(decl.id, parent.id, "extends")
            for text in decl.implements:
                parent = table.type_named(text, decl)
                if parent is not None:
                    add_edge(decl.id, parent.id, "implements")
            if mode == "types":
                continue
            for member in decl.members:
                nodes.append(_member_node(project, member, decl))
                add_edge(decl.id, member.id, "contains")

    if mode != "types":
        for member in project.members():
            for target, count in sorted(project.call_counts(member).items()):
                add_edge(member.id, target, "calls", count)
            fields, types = project.use_counts(member)
            for target, count in sorted(fields.items()):
                add_edge(member.id, target, "uses", count)
            for target, count in sorted(types.items()):
                add_edge(member.id, target, "uses", count)

    return StructureGraph(mode=mode, nodes=nodes, edges=edges, content_hash=project.content_hash)


def build_tree(project: JavaProject) -> ProjectTree:
    """Дерево «Проект»: пакеты → файлы → типы → члены (файлы без пакета — в корне)."""
    packages: dict[str, TreeNode] = {}
    roots: list[TreeNode] = []

    def type_node(decl: TypeDecl, file: str) -> TreeNode:
        span = _range(project, file, decl.start_byte, decl.end_byte)
        children: list[TreeNode] = []
        for member in decl.members:
            member_span = _range(project, file, member.start_byte, member.end_byte)
            flowable = member.kind in {"method", "constructor", "initializer"}
            children.append(
                TreeNode(
                    id=member.id,
                    kind="member",
                    name=member.key,
                    node_id=member.id,
                    method_id=member.id if flowable else None,
                    member_kind=member.kind,
                    range=member_span,
                )
            )
        children.extend(type_node(inner, file) for inner in decl.nested)
        children.sort(key=lambda n: n.range.start_line if n.range is not None else 0)
        return TreeNode(
            id=decl.id,
            kind="type",
            name=decl.name,
            node_id=decl.id,
            member_kind=decl.kind,
            range=span,
            findings=TreeBadges(),
            children=children,
        )

    for path in project.files:
        symbols = project.symbols(path)
        parsed = project.parsed(path)
        last = parsed.lines.line_count
        file_node = TreeNode(
            id=path,
            kind="file",
            name=path.rsplit("/", 1)[-1],
            range=ApiRange(path, 1, 1, last, 1),
            children=[type_node(decl, path) for decl in symbols.types],
        )
        if symbols.package:
            package = packages.get(symbols.package)
            if package is None:
                package = TreeNode(
                    id=f"pkg:{symbols.package}", kind="package", name=symbols.package
                )
                packages[symbols.package] = package
                roots.append(package)
            package.children.append(file_node)
        else:
            roots.append(file_node)
    return ProjectTree(version_id=0, roots=roots)
