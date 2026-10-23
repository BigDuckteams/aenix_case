"""Помощники тестов engine: проект из строки Java и компактный текстовый рендер блок-схемы."""

from __future__ import annotations

import os
from pathlib import Path

from engine.graph.model import FlowGraph
from engine.java.project import JavaProject

SNAPSHOTS = Path(__file__).resolve().parents[1] / "snapshots"


def project_of(source: str, path: str = "Main.java") -> JavaProject:
    return JavaProject({path: source})


def flow_of(source: str, member: str, path: str = "Main.java", owner: str = "Main") -> FlowGraph:
    """Блок-схема члена по ключу (``run()``, ``m(int)``) в типе ``owner``."""
    project = project_of(source, path)
    graph = project.flow(f"{path}#{owner}.{member}")
    assert graph is not None, f"нет члена {member}"
    return graph


def _short(node_id: str, base: str) -> str:
    if node_id == base:
        return "<m>"
    return node_id[len(base) + 1 :] if node_id.startswith(base + "/") else node_id.split("#", 1)[-1]


def render(graph: FlowGraph) -> str:
    """Узлы (вид, путь, родитель, бейджи) и рёбра в одну читаемую строку на элемент."""
    base = graph.method_id
    lines = []
    for node in graph.nodes:
        badges = " ".join(f"{b.kind}:{b.label}" for b in node.badges)
        parent = f" ^{_short(node.parent_id, base)}" if node.parent_id else ""
        lines.append(
            f"{node.kind} {_short(node.id, base)}{parent}{' [' + badges + ']' if badges else ''}"
        )
    lines.append("--")
    for edge in graph.edges:
        label = f"({edge.label})" if edge.label else ""
        lines.append(
            f"{_short(edge.source, base)} -{edge.kind}{label}-> {_short(edge.target, base)}"
        )
    lines.append("exits: " + ", ".join(_short(e, base) for e in graph.exits))
    return "\n".join(lines)


def wrap_method(body: str, header: str = "void run()") -> str:
    return f"public class Main {{\n    {header} {{\n{body}\n    }}\n}}\n"


def assert_snapshot(name: str, text: str) -> None:
    """Сверка с файлом ``tests/snapshots/<name>.txt``; ``UPDATE_SNAPSHOTS=1`` перезаписывает эталон."""
    path = SNAPSHOTS / f"{name}.txt"
    expected = text + "\n"
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected, encoding="utf-8", newline="\n")
        return
    assert path.exists(), f"нет эталона {path}: UPDATE_SNAPSHOTS=1 uv run pytest …"
    assert path.read_text(encoding="utf-8") == expected, f"снапшот {name} изменился"
