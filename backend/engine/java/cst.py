"""Помощники для обхода CST tree-sitter-java.

Модели engine хранят только байтовые смещения и строки, а не объекты ``Node``: удержанные узлы
вместе с ``start_point``/``end_point`` роняют py-tree-sitter 0.26 на Python 3.14 (docs/03 § 8).
Поэтому здесь нет ни хранения узлов, ни обращения к точкам; диапазоны берутся из ``ParsedFile``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from tree_sitter import Node

from engine.java.ts import ParsedFile

COMMENT_TYPES = frozenset({"line_comment", "block_comment"})
TYPE_DECLARATIONS = frozenset(
    {
        "class_declaration",
        "interface_declaration",
        "enum_declaration",
        "record_declaration",
        "annotation_type_declaration",
    }
)
_SPACES = re.compile(r"\s+")


def walk(node: Node) -> Iterator[Node]:
    """Обход в глубину в порядке следования кода (узел, затем потомки)."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))


def named_children(node: Node) -> list[Node]:
    """Именованные потомки без комментариев."""
    return [c for c in node.children if c.is_named and c.type not in COMMENT_TYPES]


def children_of_type(node: Node, *types: str) -> list[Node]:
    return [c for c in node.children if c.type in types]


def first_child_of_type(node: Node, *types: str) -> Node | None:
    for child in node.children:
        if child.type in types:
            return child
    return None


def squash(text: str) -> str:
    """Схлопывает пробельные последовательности: так типы попадают в ключи и подписи."""
    return _SPACES.sub(" ", text).strip()


def text_of(parsed: ParsedFile, node: Node | None) -> str:
    return "" if node is None else parsed.text(node)


def short(text: str, limit: int = 90) -> str:
    one = squash(text)
    return one if len(one) <= limit else one[: limit - 1] + "…"


def modifiers_of(parsed: ParsedFile, node: Node) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Модификаторы и аннотации объявления: ``(("public", "static"), ("Override",))``."""
    mods: list[str] = []
    annotations: list[str] = []
    for child in node.children:
        if child.type != "modifiers":
            continue
        for item in child.children:
            if item.type in {"marker_annotation", "annotation"}:
                name = item.child_by_field_name("name")
                annotations.append(text_of(parsed, name))
            elif item.type not in COMMENT_TYPES:
                mods.append(parsed.text(item))
    return tuple(mods), tuple(annotations)


def find_node(parsed: ParsedFile, start: int, end: int, types: frozenset[str]) -> Node | None:
    """Узел объявления по байтовому диапазону: наименьший узел, покрывающий диапазон."""
    node: Node | None = parsed.root.descendant_for_byte_range(start, end)
    while node is not None:
        if node.type in types and node.start_byte == start and node.end_byte == end:
            return node
        node = node.parent
    return None
