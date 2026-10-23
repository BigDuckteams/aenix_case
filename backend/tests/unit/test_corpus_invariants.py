"""Инварианты корпуса `samples/` (docs/10 § 3.2): I1 разбор и I3 покрытие графа; сквозные проверки блок-схем.

Все файлы `samples/**/*.java`, кроме `broken/` (там ошибки нужны), проходят: разбор без ошибок,
главный класс там, где он должен быть, блок-схема каждого члена без запасных блоков и потерь.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

import pytest

from engine.graph.model import FlowGraph
from engine.java import cst
from engine.java.project import JavaProject

REPO = Path(__file__).resolve().parents[3]
SAMPLES = REPO / "samples"

# Операторы, каждый из которых обязан лежать внутри какого-нибудь блока схемы (I3).
STATEMENT_TYPES = frozenset(
    {
        "local_variable_declaration",
        "expression_statement",
        "explicit_constructor_invocation",
        "if_statement",
        "for_statement",
        "enhanced_for_statement",
        "while_statement",
        "do_statement",
        "try_statement",
        "try_with_resources_statement",
        "throw_statement",
        "return_statement",
        "break_statement",
        "continue_statement",
        "yield_statement",
        "assert_statement",
        "synchronized_statement",
        "labeled_statement",
    }
)


def corpus_files() -> list[Path]:
    return sorted(
        p for p in SAMPLES.rglob("*.java") if "broken" not in p.relative_to(SAMPLES).parts
    )


def sample_roots() -> list[Path]:
    """Каталоги примеров: проект — все `.java` в каталоге с `scenarios/` (как их компилирует `verify_corpus`)."""
    return sorted(p.parent for p in SAMPLES.rglob("scenarios") if p.is_dir())


def project_of_sample(root: Path) -> JavaProject:
    files = {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in root.rglob("*.java")
        if "scenarios" not in p.relative_to(root).parts
    }
    return JavaProject(files)


def reachable(graph: FlowGraph) -> set[str]:
    """Достижимые узлы: по рёбрам схемы и от контейнера к вложенным блокам (лямбды, типы, секции)."""
    children: dict[str, list[str]] = {}
    for node in graph.nodes:
        if node.parent_id is not None:
            children.setdefault(node.parent_id, []).append(node.id)
    out: dict[str, list[str]] = {}
    known = {n.id for n in graph.nodes}
    for edge in graph.edges:
        if edge.target in known:
            out.setdefault(edge.source, []).append(edge.target)
    seen = {graph.entry}
    queue = deque([graph.entry])
    while queue:
        current = queue.popleft()
        for target in (*out.get(current, ()), *children.get(current, ())):
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


@pytest.mark.parametrize("root", sample_roots(), ids=lambda p: p.relative_to(SAMPLES).as_posix())
def test_i1_sample_parses_without_errors_and_has_a_main_class(root: Path):
    project = project_of_sample(root)
    assert project.syntax_issues() == {}
    assert project.main_classes(), "не найден main-класс"


@pytest.mark.parametrize("root", sample_roots(), ids=lambda p: p.relative_to(SAMPLES).as_posix())
def test_i3_no_statement_is_lost_in_any_flow(root: Path):
    project = project_of_sample(root)
    problems: list[str] = []
    for member in project.members():
        if member.kind not in {"method", "constructor", "initializer"} or not member.has_body:
            continue
        graph = project.flow(member.id)
        assert graph is not None
        parsed = project.parsed(project.file_of(member))
        ranges = [
            (n.range.start_line, n.range.start_col, n.range.end_line, n.range.end_col)
            for n in graph.nodes
        ]
        declaration = cst.find_node(
            parsed, member.start_byte, member.end_byte, frozenset({member.decl_type})
        )
        assert declaration is not None
        for stmt in cst.walk(declaration):
            if stmt.type not in STATEMENT_TYPES:
                continue
            span = parsed.range_of(stmt)
            box = (span.start.line, span.start.column, span.end.line, span.end.column)
            if not any(r[:2] <= box[:2] and box[2:] <= r[2:] for r in ranges):
                problems.append(
                    f"{member.key}: оператор {stmt.type} на строке {box[0]} не покрыт блоками"
                )
    assert problems == []


@pytest.mark.parametrize("root", sample_roots(), ids=lambda p: p.relative_to(SAMPLES).as_posix())
def test_flows_are_well_formed(root: Path):
    project = project_of_sample(root)
    for graph in project.flows():
        ids = [n.id for n in graph.nodes]
        assert len(ids) == len(set(ids)), f"{graph.method_id}: дубли id"
        known = set(ids)
        assert graph.entry in known and set(graph.exits) <= known
        assert graph.nodes[0].kind == "method"
        assert all(n.kind != "code" for n in graph.nodes), f"{graph.method_id}: запасной блок «Код»"
        assert all(not n.errors for n in graph.nodes), f"{graph.method_id}: ошибки в блоках"
        edge_ids = [e.id for e in graph.edges]
        assert len(edge_ids) == len(set(edge_ids))
        for node in graph.nodes:
            assert node.parent_id is None or node.parent_id in known
            assert (node.range.start_line, node.range.start_col) < (
                node.range.end_line,
                node.range.end_col,
            )
        for edge in graph.edges:
            assert edge.source in known
            if edge.kind == "call":
                assert project.member(edge.target) is not None, (
                    f"{graph.method_id}: ребро call в никуда"
                )
            else:
                assert edge.target in known, f"{graph.method_id}: ребро {edge.kind} в никуда"
        assert reachable(graph) == known, f"{graph.method_id}: недостижимые блоки"


@pytest.mark.parametrize("root", sample_roots(), ids=lambda p: p.relative_to(SAMPLES).as_posix())
def test_structure_edges_point_to_existing_nodes(root: Path):
    project = project_of_sample(root)
    graph = project.structure("methods")
    known = {n.id for n in graph.nodes}
    assert len(known) == len(graph.nodes)
    for edge in graph.edges:
        assert edge.source in known and edge.target in known, edge
    tree_ids: set[str] = set()

    def collect(nodes) -> None:  # type: ignore[no-untyped-def]
        for item in nodes:
            if item.node_id:
                tree_ids.add(item.node_id)
            collect(item.children)

    collect(project.tree().roots)
    assert tree_ids == known


def test_corpus_has_many_files_and_flows():
    """Защита от пустого параметризованного набора: корпус найден и проверяется целиком."""
    assert len(sample_roots()) >= 45
    assert len(corpus_files()) >= 45


def test_broken_files_do_not_crash_the_engine():
    for path in sorted((SAMPLES / "broken").glob("*.java")):
        header = path.read_text(encoding="utf-8").splitlines()[0]
        project = JavaProject({path.name: path.read_text(encoding="utf-8")})
        issues = project.syntax_issues()
        graphs = list(project.flows())
        structure = project.structure()
        assert project.tree().roots and structure.nodes
        if header == "// broken: syntax":
            assert issues, path.name
            for issue in issues[path.name]:
                assert issue.range.start.line >= 1 and issue.range.start.column >= 1
            # методы без ошибок остаются доступными
            assert any(g.nodes[0].kind == "method" and len(g.nodes) > 1 for g in graphs)
        else:
            assert issues == {}
        for graph in graphs:
            # на сломанном коде допустимы недостижимые блоки (код после «съеденной» скобки), но не потери
            assert graph.entry in {n.id for n in graph.nodes}
            assert len({n.id for n in graph.nodes}) == len(graph.nodes)
