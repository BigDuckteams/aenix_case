"""Основа автоисправлений (S8.1): предусловия, предложение, применение правок."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from tree_sitter import Node

from engine.edit.core import TextEdit, apply_text_edits, check_syntax, reparse
from engine.java.project import JavaProject


@dataclass(slots=True)
class Check:
    """Предусловие: проверено ли, и почему нет (docs/05 § 7)."""

    name: str
    passed: bool
    reason: str | None = None


@dataclass(slots=True)
class FixProposal:
    fix_id: str
    title: str
    summary: str
    behavior_preserving: bool
    checks: list[Check] = field(default_factory=list)
    edits: list[TextEdit] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return bool(self.edits) and all(c.passed for c in self.checks)

    def failed(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]


class Refusal(Exception):
    """Предусловие не выполнено: исправление не предлагается."""

    def __init__(self, name: str, reason: str) -> None:
        super().__init__(reason)
        self.check = Check(name, False, reason)


def refuse(name: str, reason: str) -> Refusal:
    return Refusal(name, reason)


def apply_proposal(project: JavaProject, proposal: FixProposal) -> dict[str, str]:
    """Новые файлы проекта после правок предложения; новые ``ERROR``/``MISSING`` недопустимы."""
    updated = apply_text_edits(project.files, proposal.edits)
    check_syntax(project, reparse(updated), {e.file for e in proposal.edits})
    return updated


# --- вспомогательные функции для обхода ---------------------------------------------------------------------


_DUPLICATE_SUFFIX = re.compile(r"#(\d+)$")


def duplicate_index(finding_id: str) -> int:
    """Номер находки среди одноимённых (``…#2`` → 1): какое из совпадений в операторе исправлять."""
    match = _DUPLICATE_SUFFIX.search(finding_id)
    return int(match.group(1)) - 1 if match else 0


def ancestors(node: Node) -> Iterable[Node]:
    current = node.parent
    while current is not None:
        yield current
        current = current.parent


def ensure_imports(source: str, wanted: Iterable[str]) -> TextEdit | None:
    """Правка, добавляющая недостающие ``import``; ``None`` — всё уже импортировано."""
    existing = set(re.findall(r"^import\s+(?:static\s+)?([\w.*]+);", source, flags=re.MULTILINE))
    missing = []
    for name in wanted:
        package = name.rsplit(".", 1)[0]
        if name not in existing and f"{package}.*" not in existing:
            missing.append(name)
    if not missing:
        return None
    lines = "".join(f"import {name};\n" for name in sorted(missing))
    imports = list(re.finditer(r"^import\s+[^;]+;[ \t]*\n", source, flags=re.MULTILINE))
    if imports:
        offset = len(source[: imports[-1].end()].encode("utf-8"))
        return TextEdit("", offset, offset, lines)
    package_line = re.search(r"^package\s+[^;]+;[ \t]*\n", source, flags=re.MULTILINE)
    if package_line:
        offset = len(source[: package_line.end()].encode("utf-8"))
        return TextEdit("", offset, offset, "\n" + lines)
    return TextEdit("", 0, 0, lines + "\n")
