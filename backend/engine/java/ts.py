"""Тонкая обёртка над py-tree-sitter + tree-sitter-java.

Весь код проекта, зависящий от API py-tree-sitter, живёт здесь: API менялся между версиями
0.2x, поэтому остальной engine работает только с ``ParsedFile`` и ``Node``.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import tree_sitter_java
from tree_sitter import Language, Node, Parser, Tree

from engine.graph.ranges import LineIndex, SourceRange

JAVA_LANGUAGE = Language(tree_sitter_java.language())


@dataclass(frozen=True, slots=True)
class SyntaxIssue:
    kind: str  # "error" | "missing"
    message: str
    start_byte: int
    end_byte: int
    range: SourceRange


@dataclass(slots=True)
class ParsedFile:
    source: bytes
    tree: Tree
    lines: LineIndex
    issues: list[SyntaxIssue]

    @property
    def root(self) -> Node:
        return self.tree.root_node

    @property
    def ok(self) -> bool:
        return not self.issues

    def text(self, node: Node) -> str:
        return self.source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    def range_of(self, node: Node) -> SourceRange:
        return self.lines.range(node.start_byte, node.end_byte)


def parse(source: str | bytes) -> ParsedFile:
    """Разобрать Java-текст. Parser создаётся на каждый вызов: он не потокобезопасен, но дёшев."""
    data = source.encode("utf-8") if isinstance(source, str) else source
    tree = Parser(JAVA_LANGUAGE).parse(data)
    lines = LineIndex(data)
    return ParsedFile(data, tree, lines, list(_collect_issues(tree.root_node, lines)))


def _collect_issues(root: Node, lines: LineIndex) -> Iterator[SyntaxIssue]:
    stack = [root]
    while stack:
        node = stack.pop()
        if not node.has_error and not node.is_missing:
            continue
        if node.is_missing:
            yield SyntaxIssue(
                "missing",
                f"Ожидалось: {node.type}",
                node.start_byte,
                node.end_byte,
                lines.range(node.start_byte, node.end_byte),
            )
        elif node.type == "ERROR":
            yield SyntaxIssue(
                "error",
                "Синтаксическая ошибка",
                node.start_byte,
                node.end_byte,
                lines.range(node.start_byte, node.end_byte),
            )
        stack.extend(reversed(node.children))
