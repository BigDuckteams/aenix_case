"""Граф структуры и дерево «Проект» (S2.8)."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.graph.model import StructureGraph
from engine.java.project import JavaProject
from tests.unit.engine_helpers import assert_snapshot, project_of

REPO = Path(__file__).resolve().parents[3]

SOURCE = """
package shop;

interface Shape { double area(); }
abstract class Base implements Shape { int size; void touch() { size++; } }
class Circle extends Base { double r; public double area() { return r * r; } }
public class Main {
    private final Circle circle = new Circle();
    private int count;
    static class Helper { static int twice(int x) { return x * 2; } }
    enum Mode { A, B }
    void run() { helper(); count++; circle.area(); Helper.twice(count); }
    void helper() { run(); this.count = 1; }
    static void main(String[] args) { new Main().run(); Mode m = Mode.A; }
}
"""


@pytest.fixture(scope="module")
def graph() -> StructureGraph:
    return project_of(SOURCE).structure("methods")


def edges(graph: StructureGraph, kind: str) -> set[tuple[str, str, int]]:
    def short(i: str) -> str:
        return i.split("#", 1)[1]

    return {(short(e.source), short(e.target), e.weight) for e in graph.edges if e.kind == kind}


def test_nodes_cover_types_and_members(graph):
    types = {n.name: n for n in graph.nodes if n.node_type == "type"}
    assert set(types) == {"Shape", "Base", "Circle", "Main", "Helper", "Mode"}
    assert types["Shape"].kind == "interface" and types["Mode"].kind == "enum"
    assert types["Helper"].parent_id == "Main.java#Main"
    assert types["Main"].parent_id is None
    run = next(n for n in graph.nodes if n.id == "Main.java#Main.run()")
    assert (run.node_type, run.kind, run.method_id) == ("member", "method", run.id)
    assert run.parent_id == "Main.java#Main" and run.signature == "run()"
    count = next(n for n in graph.nodes if n.id == "Main.java#Main.count")
    assert count.kind == "field" and count.method_id is None and "private" in count.modifiers
    assert run.range.start_line == run.range.end_line == 12


def test_inheritance_and_containment_edges(graph):
    assert edges(graph, "implements") == {("Base", "Shape", 1)}
    assert edges(graph, "extends") == {("Circle", "Base", 1)}
    contains = edges(graph, "contains")
    assert ("Main", "Main.run()", 1) in contains
    assert ("Main", "Main.Helper", 1) in contains
    assert ("Main.Helper", "Main.Helper.twice(int)", 1) in contains
    assert ("Main", "Main.Mode", 1) in contains


def test_call_edges_with_weights_and_recursion(graph):
    calls = edges(graph, "calls")
    assert ("Main.run()", "Main.helper()", 1) in calls
    assert ("Main.helper()", "Main.run()", 1) in calls  # взаимная рекурсия
    # получатель объявлен как Circle: вызывается Circle.area, а не абстрактный Shape.area
    assert ("Main.run()", "Circle.area()", 1) in calls
    assert ("Main.run()", "Shape.area()", 1) not in calls
    assert ("Main.run()", "Main.Helper.twice(int)", 1) in calls
    assert ("Main.main(String[])", "Main.run()", 1) in calls


def test_uses_edges_to_fields_and_types(graph):
    uses = edges(graph, "uses")
    assert ("Main.run()", "Main.count", 2) in uses
    assert ("Main.helper()", "Main.count", 1) in uses  # this.count
    assert ("Main.run()", "Main.circle", 1) in uses
    assert ("Main.run()", "Main.Helper", 1) in uses  # тип через статический вызов
    assert ("Main.main(String[])", "Main.Mode", 2) in uses  # тип переменной и получатель Mode.A
    assert ("Base.touch()", "Base.size", 1) in uses
    assert not any(src == tgt for src, tgt, _ in uses)


def test_types_mode_has_no_members_and_no_calls():
    types = project_of(SOURCE).structure("types")
    assert {n.node_type for n in types.nodes} == {"type"}
    assert {e.kind for e in types.edges} == {"contains", "extends", "implements"}


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError, match="режим"):
        project_of(SOURCE).structure("everything")


def test_project_tree_groups_by_package_file_type_member():
    tree = project_of(SOURCE).tree()
    assert [r.kind for r in tree.roots] == ["package"]
    package = tree.roots[0]
    assert (package.name, package.id) == ("shop", "pkg:shop")
    file = package.children[0]
    assert (file.kind, file.name) == ("file", "Main.java")
    assert [c.name for c in file.children] == ["Shape", "Base", "Circle", "Main"]
    main = next(c for c in file.children if c.name == "Main")
    names = [c.name for c in main.children]
    assert names[:2] == ["circle", "count"]
    assert "Helper" in names and "Mode" in names
    method = next(c for c in main.children if c.name == "run()")
    assert method.method_id == "Main.java#Main.run()" and method.member_kind == "method"
    # типы и члены в порядке следования в файле
    lines = [c.range.start_line for c in main.children]
    assert lines == sorted(lines)


def test_tree_without_package_keeps_files_in_the_root():
    tree = project_of("class A {}").tree()
    assert [(r.kind, r.name) for r in tree.roots] == [("file", "Main.java")]


def test_two_files_resolve_types_across_files():
    project = JavaProject(
        {
            "a/Util.java": "class Util { static int f() { return 1; } }",
            "Main.java": "class Main { void run() { Util.f(); } }",
        }
    )
    graph = project.structure()
    calls = {(e.source, e.target) for e in graph.edges if e.kind == "calls"}
    assert ("Main.java#Main.run()", "a/Util.java#Util.f()") in calls


def test_demo_orders_structure_snapshot():
    source = (REPO / "samples" / "demo-orders" / "Main.java").read_text(encoding="utf-8")
    graph = JavaProject({"Main.java": source}).structure("methods")
    lines = []
    for kind in ("extends", "implements"):
        lines += sorted(f"{kind} {e.source} -> {e.target}" for e in graph.edges if e.kind == kind)
    calls = sorted(
        f"{e.source.split('#', 1)[1]} -> {e.target.split('#', 1)[1]} x{e.weight}"
        for e in graph.edges
        if e.kind == "calls"
    )
    counts = {k: sum(e.kind == k for e in graph.edges) for k in ("contains", "calls", "uses")}
    assert_snapshot("structure/demo-orders", "\n".join([*lines, f"counts {counts}", *calls]))
