"""Пакет операций: атомарное применение, фокус и соответствие старых и новых id (S5.8)."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from engine.edit.core import EditError, unsupported
from engine.edit.operations import HANDLERS, Editor, EditResult
from engine.edit.symbols import (
    op_add_member,
    op_delete_member,
    op_rename_symbol,
    op_update_member,
)
from engine.graph.ranges import Position
from engine.java.project import FLOWABLE, JavaProject, get_project

ALL_HANDLERS = {
    **HANDLERS,
    "rename_symbol": op_rename_symbol,
    "add_member": op_add_member,
    "update_member": op_update_member,
    "delete_member": op_delete_member,
}


def apply_ops(files: dict[str, str], ops: list[dict[str, Any]]) -> EditResult:
    """Применяет операции по порядку к копии файлов; при ошибке любой операции — ``EditError``.

    Идентификаторы в каждой следующей операции относятся к состоянию после предыдущих.
    """
    editor = Editor(files)
    for index, op in enumerate(ops):
        handler = ALL_HANDLERS.get(op["op"])
        try:
            if handler is None:
                raise unsupported(f"операция «{op['op']}» не поддерживается")
            handler(editor, op)
        except EditError as error:
            error.op_index = index
            raise
    before = get_project(files)
    after = editor.project
    changed = sorted(p for p in editor.changed if editor.files.get(p) != files.get(p))
    return EditResult(
        files=editor.files,
        changed=changed,
        focus_node_id=_focus(after, editor.focus),
        id_map=_id_map(before, after, changed),
    )


def _focus(project: JavaProject, focus: tuple[str, int] | None) -> str | None:
    if focus is None:
        return None
    file, offset = focus
    if file not in project.files:
        return None
    size = len(project.files[file].encode("utf-8"))
    point = project.parsed(file).lines.range(min(offset, size), min(offset, size)).start
    found = project.locate(file, point.line, point.column)
    return found.node_id if found is not None else None


def _signature(project: JavaProject, method_id: str) -> list[tuple[str, str]]:
    graph = project.flow(method_id)
    if graph is None:
        return []
    return [(n.kind, n.code) for n in graph.nodes]


def _id_map(before: JavaProject, after: JavaProject, changed: list[str]) -> dict[str, str]:
    """Старый id → новый для блоков, чьи id изменились (сопоставление по виду и тексту блока)."""
    mapping: dict[str, str] = {}
    for member in before.members():
        if member.kind not in FLOWABLE or before.file_of(member) not in changed:
            continue
        old_graph = before.flow(member.id)
        new_graph = after.flow(member.id)
        if old_graph is None or new_graph is None:
            continue
        matcher = SequenceMatcher(
            None, _signature(before, member.id), _signature(after, member.id), autojunk=False
        )
        for block in matcher.get_matching_blocks():
            for offset in range(block.size):
                old_id = old_graph.nodes[block.a + offset].id
                new_id = new_graph.nodes[block.b + offset].id
                if old_id != new_id:
                    mapping[old_id] = new_id
    return mapping


def validate_batch(
    files: dict[str, str], ops: list[dict[str, Any]]
) -> tuple[EditResult | None, EditError | None]:
    """Сухая проверка: результат пакета либо первая ошибка."""
    try:
        return apply_ops(files, ops), None
    except EditError as error:
        return None, error


__all__ = ["EditError", "EditResult", "Position", "apply_ops", "validate_batch"]
