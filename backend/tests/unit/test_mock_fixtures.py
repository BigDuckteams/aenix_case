"""Моки frontend (S1.2): фикстуры соответствуют схемам контракта и согласованы друг с другом."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from app.schemas.analysis import AnalysisResponse
from app.schemas.graph import FlowGraph, ProjectTree, StructureGraph
from app.schemas.verify import RunEvent, RunInfo, ScenarioList

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "frontend" / "src" / "mocks" / "fixtures"
DEMO = REPO / "samples" / "demo-orders"


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


FLOWS: dict[str, dict] = load("flows")
FLOW_IDS = sorted(FLOWS)
MERGE = "Main.java#Main.mergeDuplicates()"


def test_fixtures_are_up_to_date_with_generator():
    """Генератор читает samples/demo-orders и схемы; расхождение значит, что моки нужно перегенерировать."""
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "gen_mock_fixtures.py"), "--check"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO / "backend",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.parametrize("method_id", FLOW_IDS)
def test_flow_graph_is_consistent(method_id):
    flow = FlowGraph.model_validate(FLOWS[method_id])
    ids = {n.id for n in flow.nodes}
    assert len(ids) == len(flow.nodes), "дубли id узлов"
    assert flow.entry in ids and set(flow.exits) <= ids
    assert flow.nodes[0].kind == "method" and flow.nodes[0].id == flow.method_id == method_id
    for node in flow.nodes:
        assert node.parent_id is None or node.parent_id in ids
        assert node.range.start_line <= node.range.end_line
    edge_ids = [e.id for e in flow.edges]
    assert len(edge_ids) == len(set(edge_ids))
    for edge in flow.edges:
        assert edge.source in ids
        if edge.kind == "call":  # ребро call ведёт в схему другого метода
            assert edge.target in FLOWS, edge
        else:
            assert edge.target in ids, edge
    # каждый узел достижим из входа: по рёбрам и от контейнера к вложенным блокам
    reachable, stack = {flow.entry}, [flow.entry]
    while stack:
        current = stack.pop()
        nxt = [e.target for e in flow.edges if e.source == current] + [
            n.id for n in flow.nodes if n.parent_id == current
        ]
        for target in nxt:
            if target in ids and target not in reachable:
                reachable.add(target)
                stack.append(target)
    assert reachable == ids


def test_main_flow_has_loop_condition_and_call_in_15_to_20_nodes():
    flow = FlowGraph.model_validate(FLOWS[MERGE])
    kinds = {n.kind for n in flow.nodes}
    assert 15 <= len(flow.nodes) <= 20
    assert {"method", "loop_foreach", "condition", "operation", "return", "break"} <= kinds
    assert any(b.kind == "call" for n in flow.nodes for b in n.badges)
    assert {e.kind for e in flow.edges} >= {"next", "true", "body", "back", "break"}
    assert any(n.complexity == "O(n·m)" for n in flow.nodes)


def test_flow_ranges_match_the_source_file():
    source = (DEMO / "Main.java").read_text(encoding="utf-8").splitlines()
    flow = FlowGraph.model_validate(FLOWS["Main.java#Main.buildCsv()"])
    loop = next(n for n in flow.nodes if n.kind == "loop_foreach")
    assert source[loop.range.start_line - 1].strip().startswith("for (Order order : orders)")
    assert "csv +=" in source[loop.range.start_line]


def test_mock_file_equals_the_sample():
    content = load("file-main")["content"]
    assert content == (DEMO / "Main.java").read_text(encoding="utf-8")


def test_structure_tree_and_flows_agree():
    structure = StructureGraph.model_validate(load("structure"))
    tree = ProjectTree.model_validate(load("tree"))
    ids = {n.id for n in structure.nodes}
    assert len(ids) == len(structure.nodes)
    for edge in structure.edges:
        assert edge.source in ids and edge.target in ids, edge
    assert {e.kind for e in structure.edges} == {"contains", "calls", "implements", "uses"}
    method_ids = {n.method_id for n in structure.nodes if n.method_id}
    assert set(FLOWS) == method_ids, (
        "блок-схема есть у каждого метода, конструктора и инициализатора"
    )

    def collect(nodes) -> set[str]:
        found = set()
        for node in nodes:
            if node.node_id:
                found.add(node.node_id)
            found |= collect(node.children)
        return found

    assert collect(tree.roots) == ids
    types = [n for n in structure.nodes if n.node_type == "type"]
    assert {"Main", "Order", "OrderStatus", "CustomerTotal"} <= {t.name for t in types}
    assert sum(1 for n in structure.nodes if n.kind == "method") >= 60


def test_findings_point_at_real_nodes():
    analysis = AnalysisResponse.model_validate(load("findings"))
    structure = {n["id"] for n in load("structure")["nodes"]}
    flow_nodes = {n["id"] for flow in FLOWS.values() for n in flow["nodes"]}
    rules = {f.rule_id for f in analysis.findings}
    assert {"PERF-01", "PERF-02", "PERF-03", "BUG-01", "BUG-02", "MAINT-01", "MAINT-05"} <= rules
    assert len({f.id for f in analysis.findings}) == len(analysis.findings)
    for finding in analysis.findings:
        if finding.location.node_id:
            assert finding.location.node_id in flow_nodes | structure, finding.id
        if finding.location.method_id:
            assert finding.location.method_id in structure, finding.id
        assert finding.id.startswith(finding.rule_id + ":")
    assert analysis.summary.total == len(analysis.findings)
    assert sum(analysis.summary.by_severity.values()) == analysis.summary.total
    fixes = load("fixes")["fixes"]
    assert {f["finding_id"] for f in fixes} <= {f.id for f in analysis.findings}
    defects = {
        b["ref"]
        for flow in FLOWS.values()
        for n in flow["nodes"]
        for b in n["badges"]
        if b["kind"] == "defect"
    }
    assert defects <= {f.id for f in analysis.findings}


def test_scenarios_and_runs_match_the_sample():
    scenarios = ScenarioList.model_validate(load("scenarios")).scenarios
    sample = {p.stem for p in (DEMO / "scenarios").glob("*.json")}
    assert {s.name for s in scenarios} == sample
    ids = {s.id for s in scenarios}
    for name in ("run-7", "run-8"):
        run = RunInfo.model_validate(load(name))
        assert {i.scenario_id for i in run.items} == ids
        assert run.summary.total == len(ids)
        assert run.summary.passed == sum(i.verdict == "PASS" for i in run.items)
    failed = [i for i in RunInfo.model_validate(load("run-8")).items if i.verdict == "FAIL"]
    assert len(failed) == 1 and failed[0].diff and failed[0].diff.stdout


def test_run_events_replay_is_a_valid_stream():
    events = TypeAdapter(list[RunEvent]).validate_python(load("run-8-events"))
    assert [e.event for e in events[:2]] == ["status", "status"]
    assert events[0].data.status == "queued"
    assert events[-1].event == "done"
    assert events[-2].data.status == "done"
    kinds = {e.event for e in events}
    assert {"status", "log", "gate", "item", "progress", "result", "done"} <= kinds
    progress = [e.data for e in events if e.event == "progress"]
    assert [p.done for p in progress] == list(range(1, len(progress) + 1))
    assert all(p.total == len(progress) for p in progress)
    items = [e for e in events if e.event == "item"]
    assert len(items) == len(progress)
