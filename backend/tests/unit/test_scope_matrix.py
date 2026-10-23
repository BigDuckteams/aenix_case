"""Матрица scope (docs/04 § 9.4): каждая фикстура разбирается и даёт ожидаемые виды блоков.

`expected_kinds.json` перечисляет виды блоков, которые обязаны появиться хотя бы в одной блок-схеме
фикстуры. Тест читает их у настоящего построителя графа (S2), так что файл — живая спецификация.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.java.project import JavaProject

REPO = Path(__file__).resolve().parents[3]
SCOPE = REPO / "samples" / "scope"
FIXTURES = sorted(p for p in SCOPE.iterdir() if p.is_dir())


def project_of_fixture(fixture: Path) -> JavaProject:
    return JavaProject({"Main.java": (fixture / "Main.java").read_text(encoding="utf-8")})


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda p: p.name)
def test_fixture_yields_the_expected_block_kinds(fixture: Path):
    project = project_of_fixture(fixture)
    assert project.syntax_issues() == {}
    expected = set(
        json.loads((fixture / "expected_kinds.json").read_text(encoding="utf-8"))["kinds"]
    )
    present: set[str] = set()
    graphs = list(project.flows())
    assert graphs, "в фикстуре нет ни одного метода"
    for graph in graphs:
        present |= {n.kind for n in graph.nodes}
    missing = expected - present
    assert not missing, f"{fixture.name}: нет блоков {sorted(missing)}; есть {sorted(present)}"


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda p: p.name)
def test_fixture_symbols_and_structure_are_complete(fixture: Path):
    project = project_of_fixture(fixture)
    assert project.main_classes() == ["Main"]
    types = list(project.types())
    assert any(t.name == "Main" for t in types)
    structure = project.structure("methods")
    assert {n.name for n in structure.nodes if n.node_type == "type"} >= {t.name for t in types}
    # у каждого метода и конструктора с телом есть блок-схема из более чем одного блока или пустое тело
    for member in project.members():
        if member.kind in {"method", "constructor"} and member.has_body:
            graph = project.flow(member.id)
            assert graph is not None and graph.nodes[0].kind == "method"


def test_bonus_constructs_are_visible_in_the_graph():
    """Бонусный scope (record, enum, дженерики, лямбды, Stream) попадает в граф, а не в запасной блок."""
    record = project_of_fixture(SCOPE / "b1-record")
    assert {t.kind for t in record.types()} >= {"record"}
    assert any(m.role == "compact_constructor" for m in record.members())
    enum = project_of_fixture(SCOPE / "b1-enum")
    assert {t.kind for t in enum.types()} >= {"enum"}
    assert any(m.role == "constant" for m in enum.members())
    generics = project_of_fixture(SCOPE / "b2-generics")
    assert any(t.type_params for t in generics.types())
    assert any(m.type_params for m in generics.members())
    lambdas = project_of_fixture(SCOPE / "b3-lambda")
    assert any(n.kind == "lambda" for g in lambdas.flows() for n in g.nodes)
    streams = project_of_fixture(SCOPE / "b4-stream")
    assert any("pipelines" in n.data for g in streams.flows() for n in g.nodes)


def test_io_fixtures_show_input_and_output_badges():
    for name, kind in (("02-output", "output"), ("02-scanner", "input"), ("02-reader", "input")):
        project = project_of_fixture(SCOPE / name)
        badges = {b.kind for g in project.flows() for n in g.nodes for b in n.badges}
        assert kind in badges, f"{name}: нет бейджа {kind}"
    stderr = project_of_fixture(SCOPE / "02-output")
    assert "error_output" in {b.kind for g in stderr.flows() for n in g.nodes for b in n.badges}


def test_exception_fixtures_have_try_throw_and_exception_edges():
    project = project_of_fixture(SCOPE / "04-custom")
    kinds = {n.kind for g in project.flows() for n in g.nodes}
    edge_kinds = {e.kind for g in project.flows() for e in g.edges}
    assert {"try", "catch", "throw"} <= kinds
    assert "exception" in edge_kinds
