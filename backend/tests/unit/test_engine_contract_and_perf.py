"""Модели engine совпадают со схемами API; кеш по содержимому; бюджет времени (S2.9, docs/10 § 3.6)."""

from __future__ import annotations

import dataclasses
import time
from pathlib import Path

import pytest
from pydantic import BaseModel

from app.schemas import graph as api
from engine.graph import model
from engine.java.project import JavaProject, content_hash_of, get_project

REPO = Path(__file__).resolve().parents[3]
DEMO = (REPO / "samples" / "demo-orders" / "Main.java").read_text(encoding="utf-8")

PAIRS: list[tuple[type, type[BaseModel]]] = [
    (model.FlowNode, api.FlowNode),
    (model.FlowEdge, api.FlowEdge),
    (model.FlowGraph, api.FlowGraph),
    (model.Badge, api.Badge),
    (model.StructureNode, api.StructureNode),
    (model.StructureEdge, api.StructureEdge),
    (model.StructureGraph, api.StructureGraph),
    (model.TreeNode, api.TreeNode),
    (model.TreeBadges, api.TreeBadges),
    (model.ProjectTree, api.ProjectTree),
]


@pytest.mark.parametrize(
    ("engine_cls", "schema"), PAIRS, ids=lambda x: getattr(x, "__name__", str(x))
)
def test_engine_models_have_the_same_fields_as_api_schemas(engine_cls, schema):
    assert {f.name for f in dataclasses.fields(engine_cls)} == set(schema.model_fields)


def test_engine_range_matches_api_source_range():
    from app.schemas.common import SourceRange

    assert {f.name for f in dataclasses.fields(model.ApiRange)} == set(SourceRange.model_fields)


def test_demo_orders_graphs_validate_against_the_api_schemas():
    project = JavaProject({"Main.java": DEMO})
    flows = list(project.flows())
    assert len(flows) > 80
    for graph in flows:
        validated = api.FlowGraph.model_validate(dataclasses.asdict(graph))
        assert validated.nodes[0].kind == "method"
    for mode in ("types", "methods", "deps"):
        api.StructureGraph.model_validate(dataclasses.asdict(project.structure(mode)))
    api.ProjectTree.model_validate(dataclasses.asdict(project.tree()))


def test_corpus_flows_use_only_kinds_the_contract_allows():
    from typing import get_args

    node_kinds = set(get_args(api.NodeKind))
    edge_kinds = set(get_args(api.EdgeKind))
    project = JavaProject({"Main.java": DEMO})
    for graph in project.flows():
        assert {n.kind for n in graph.nodes} <= node_kinds
        assert {e.kind for e in graph.edges} <= edge_kinds


def test_content_hash_depends_on_paths_and_text_only():
    files = {"A.java": "class A {}", "B.java": "class B {}"}
    assert content_hash_of(files) == content_hash_of(dict(reversed(list(files.items()))))
    assert content_hash_of(files) != content_hash_of({**files, "B.java": "class B { }"})
    assert content_hash_of(files) != content_hash_of(
        {"A.java": "class A {}", "C.java": "class B {}"}
    )


def test_get_project_returns_the_cached_instance_for_equal_content():
    files = {"Main.java": "class Main { void f() {} }"}
    first = get_project(files)
    assert get_project(dict(files)) is first
    other = get_project({"Main.java": "class Main { void g() {} }"})
    assert other is not first
    assert first.flow("Main.java#Main.f()") is first.flow("Main.java#Main.f()")


def test_flow_of_unknown_or_non_flowable_member_is_none():
    project = JavaProject({"Main.java": "class Main { int x; void f() {} }"})
    assert project.flow("Main.java#Main.x") is None
    assert project.flow("Main.java#Main.nothing()") is None


def test_parse_and_build_all_graphs_of_demo_orders_within_budget():
    """Бюджет: разбор + граф 1000 строк ≤ 300 мс (docs/10 § 3.6), холодный запуск."""
    best = float("inf")
    for _ in range(3):
        started = time.perf_counter()
        project = JavaProject({"Main.java": DEMO})
        flows = list(project.flows())
        project.structure("methods")
        project.tree()
        best = min(best, time.perf_counter() - started)
    assert len(flows) > 80
    assert best < 0.3, f"{best * 1000:.0f} мс"


def test_warm_cache_makes_repeated_flow_requests_cheap():
    project = JavaProject({"Main.java": DEMO})
    member = "Main.java#Main.printReport()"
    project.flow(member)
    started = time.perf_counter()
    for _ in range(200):
        project.flow(member)
    assert time.perf_counter() - started < 0.05
