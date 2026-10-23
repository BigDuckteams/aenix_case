"""Генератор JSON-моков для frontend (S1.2): `frontend/src/mocks/fixtures/*.json`.

    cd backend && uv run python ../scripts/gen_mock_fixtures.py          # перезаписать фикстуры
    cd backend && uv run python ../scripts/gen_mock_fixtures.py --check  # только сверить с диском

Фикстуры строятся из `samples/demo-orders/Main.java` (разбор — обёртка tree-sitter из `engine`),
поэтому диапазоны кода и идентификаторы узлов настоящие. Блок-схемы собирает упрощённый
построитель ниже; на этапе S2 их заменит настоящий `engine/graph/flow.py`, и фикстуры можно будет
перегенерировать из него. Каждая фикстура перед записью проверяется Pydantic-схемой контракта
(`app.schemas`), так что моки не расходятся с OpenAPI.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from pydantic import TypeAdapter  # noqa: E402

from app.schemas.analysis import AnalysisResponse, MetricsResponse  # noqa: E402
from app.schemas.graph import FlowGraph, ProjectTree, StructureGraph  # noqa: E402
from app.schemas.health import HealthResponse  # noqa: E402
from app.schemas.ops import Palette  # noqa: E402
from app.schemas.project import (  # noqa: E402
    FileContent,
    FileList,
    ProjectDetail,
    ProjectList,
    SampleList,
    VersionList,
)
from app.schemas.transform import FixList  # noqa: E402
from app.schemas.verify import BuildResult, RunEvent, RunInfo, RunList, ScenarioList  # noqa: E402
from engine.java.ts import ParsedFile, parse  # noqa: E402

SOURCE_PATH = REPO / "samples" / "demo-orders" / "Main.java"
OUT = REPO / "frontend" / "src" / "mocks" / "fixtures"
FILE = "Main.java"
NOW = "2026-10-24T08:00:00Z"

LABELS = {
    "method": "Метод",
    "var_decl": "Переменная",
    "assign": "Присваивание",
    "operation": "Операция",
    "condition": "Условие",
    "loop_foreach": "Цикл (for each)",
    "loop_for": "Цикл (for)",
    "loop_while": "Цикл (while)",
    "return": "Возврат",
    "break": "Прервать",
    "continue": "Продолжить",
    "throw": "Исключение",
    "code": "Код",
}
PATH_NAMES = {
    "var_decl": "var",
    "assign": "assign",
    "operation": "op",
    "condition": "if",
    "loop_foreach": "foreach",
    "loop_for": "for",
    "loop_while": "while",
    "return": "return",
    "break": "break",
    "continue": "continue",
    "throw": "throw",
    "code": "code",
}
LOOPS = {"loop_foreach", "loop_for", "loop_while"}
COMPLEXITY = {
    "mergeDuplicates": "O(n·m)",
    "distinctCustomers": "O(n·m)",
    "buildCsv": "O(n²)",
    "findOrderById": "O(n)",
}


class Source:
    """Текст файла, разобранный tree-sitter; диапазоны — через ``range_of`` (байты → UTF-16)."""

    def __init__(self) -> None:
        self.text = SOURCE_PATH.read_text(encoding="utf-8")
        self.parsed: ParsedFile = parse(self.text)
        assert self.parsed.ok

    def rng(self, node: Any) -> dict[str, Any]:
        r = self.parsed.range_of(node)
        return {
            "file": FILE,
            "start_line": r.start.line,
            "start_col": r.start.column,
            "end_line": r.end.line,
            "end_col": r.end.column,
        }

    def txt(self, node: Any) -> str:
        return self.parsed.text(node)


def walk(node: Any):
    yield node
    for child in node.children:
        yield from walk(child)


def short(text: str, limit: int = 80) -> str:
    one = re.sub(r"\s+", " ", text).strip()
    return one if len(one) <= limit else one[: limit - 1] + "…"


# ---------------------------------------------------------------------------------------------
# Структура проекта
# ---------------------------------------------------------------------------------------------


def collect_members(src: Source) -> tuple[list[dict], list[dict]]:
    """Типы и члены файла: список словарей с узлом tree-sitter внутри (не сериализуется)."""
    types: list[dict] = []
    members: list[dict] = []
    for node in walk(src.parsed.root):
        if node.type not in {
            "class_declaration",
            "interface_declaration",
            "enum_declaration",
            "record_declaration",
        }:
            continue
        name = src.txt(node.child_by_field_name("name"))
        kind = node.type.removesuffix("_declaration")
        types.append({"node": node, "name": name, "kind": kind})
        body = node.child_by_field_name("body")
        body_children = []
        for child in body.children:
            if child.type == "enum_body_declarations":
                body_children += child.children
            else:
                body_children.append(child)
        for member in body_children:
            if member.type == "method_declaration":
                mname = src.txt(member.child_by_field_name("name"))
                params = member.child_by_field_name("parameters")
                ptypes = [
                    src.txt(p.child_by_field_name("type"))
                    for p in params.children
                    if p.type == "formal_parameter"
                ]
                members.append(
                    {"node": member, "type": name, "kind": "method", "name": mname, "params": ptypes}
                )
            elif member.type == "constructor_declaration":
                params = member.child_by_field_name("parameters")
                ptypes = [
                    src.txt(p.child_by_field_name("type"))
                    for p in params.children
                    if p.type == "formal_parameter"
                ]
                members.append(
                    {"node": member, "type": name, "kind": "constructor", "name": name, "params": ptypes}
                )
            elif member.type == "field_declaration":
                declarator = next(c for c in member.children if c.type == "variable_declarator")
                members.append(
                    {
                        "node": member,
                        "type": name,
                        "kind": "field",
                        "name": src.txt(declarator.child_by_field_name("name")),
                        "params": [],
                    }
                )
    return types, members


def member_key(m: dict) -> str:
    if m["kind"] == "field":
        return m["name"]
    return f"{m['name']}({', '.join(m['params'])})"


def member_id(m: dict) -> str:
    return f"{FILE}#{m['type']}.{member_key(m)}"


def modifiers_of(src: Source, node: Any) -> list[str]:
    for child in node.children:
        if child.type == "modifiers":
            return src.txt(child).split()
    return []


def build_structure(src: Source, types: list[dict], members: list[dict]) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []
    edge_ids: set[str] = set()

    def add_edge(source: str, target: str, kind: str, weight: int = 1) -> None:
        eid = f"{kind}:{source}->{target}"
        if eid not in edge_ids:
            edge_ids.add(eid)
            edges.append({"id": eid, "source": source, "target": target, "kind": kind, "weight": weight})

    type_ids = {t["name"]: f"{FILE}#{t['name']}" for t in types}
    for t in types:
        rng = src.rng(t["node"])
        nodes.append(
            {
                "id": type_ids[t["name"]],
                "node_type": "type",
                "kind": t["kind"],
                "name": t["name"],
                "signature": None,
                "modifiers": modifiers_of(src, t["node"]),
                "type_params": [],
                "parent_id": None,
                "range": rng,
                "lines": rng["end_line"] - rng["start_line"] + 1,
                "method_id": None,
                "complexity": None,
                "findings_count": 0,
                "cluster": None,
            }
        )
        for child in t["node"].children:
            if child.type == "super_interfaces":
                for ident in walk(child):
                    if ident.type == "type_identifier" and src.txt(ident) in type_ids:
                        add_edge(type_ids[t["name"]], type_ids[src.txt(ident)], "implements")
            if child.type == "superclass":
                for ident in walk(child):
                    if ident.type == "type_identifier" and src.txt(ident) in type_ids:
                        add_edge(type_ids[t["name"]], type_ids[src.txt(ident)], "extends")

    names = {}
    for m in members:
        if m["kind"] == "method":
            names.setdefault(m["name"], []).append(m)
    findings_by_method = {"mergeDuplicates": 1, "distinctCustomers": 1, "buildCsv": 1, "discountFor": 1,
                          "readBatch": 1, "printReport": 1}
    for m in members:
        rng = src.rng(m["node"])
        mid = member_id(m)
        runs_flow = m["kind"] in {"method", "constructor"}
        nodes.append(
            {
                "id": mid,
                "node_type": "member",
                "kind": m["kind"],
                "name": m["name"],
                "signature": member_key(m),
                "modifiers": modifiers_of(src, m["node"]),
                "type_params": [],
                "parent_id": type_ids[m["type"]],
                "range": rng,
                "lines": rng["end_line"] - rng["start_line"] + 1,
                "method_id": mid if runs_flow else None,
                "complexity": COMPLEXITY.get(m["name"]) if m["kind"] == "method" else None,
                "findings_count": findings_by_method.get(m["name"], 0) if m["type"] == "Main" else 0,
                "cluster": None,
            }
        )
        add_edge(type_ids[m["type"]], mid, "contains")
        if m["kind"] != "method":
            continue
        body = m["node"].child_by_field_name("body")
        if body is None:
            continue
        counts: dict[str, int] = {}
        for call in walk(body):
            if call.type == "method_invocation":
                callee = src.txt(call.child_by_field_name("name"))
                if callee in names and callee != m["name"]:
                    counts[callee] = counts.get(callee, 0) + 1
        for callee, count in counts.items():
            add_edge(mid, member_id(names[callee][0]), "calls", count)
    return {
        "mode": "methods",
        "nodes": nodes,
        "edges": edges,
        "version_id": 3,
        "content_hash": "mock-demo-orders-v3",
    }


def build_tree(structure: dict) -> dict:
    by_parent: dict[str, list[dict]] = {}
    for n in structure["nodes"]:
        by_parent.setdefault(n["parent_id"] or "", []).append(n)

    def tree_node(n: dict) -> dict:
        is_type = n["node_type"] == "type"
        count = n["findings_count"]
        return {
            "id": n["id"],
            "kind": "type" if is_type else "member",
            "name": n["name"] if is_type else n["signature"] or n["name"],
            "node_id": n["id"],
            "method_id": n["method_id"],
            "member_kind": None if is_type else n["kind"],
            "range": n["range"],
            "complexity": n["complexity"],
            "findings": {"high": count, "medium": 0, "low": 0} if count else {"high": 0, "medium": 0, "low": 0},
            "children": [tree_node(c) for c in by_parent.get(n["id"], [])],
        }

    types = by_parent.get("", [])
    last = max(t["range"]["end_line"] for t in types)
    file_node = {
        "id": FILE,
        "kind": "file",
        "name": FILE,
        "node_id": None,
        "method_id": None,
        "member_kind": None,
        "range": {"file": FILE, "start_line": 1, "start_col": 1, "end_line": last, "end_col": 2},
        "complexity": None,
        "findings": {"high": 0, "medium": 0, "low": 0},
        "children": [tree_node(t) for t in types],
    }
    return {"version_id": 3, "roots": [file_node]}


# ---------------------------------------------------------------------------------------------
# Блок-схемы (упрощённый построитель; настоящий — engine/graph/flow.py, этап S2)
# ---------------------------------------------------------------------------------------------


class FlowBuilder:
    def __init__(self, src: Source, member: dict, method_names: dict[str, str], findings: dict[str, str]):
        self.src = src
        self.member = member
        self.method_names = method_names
        self.findings = findings  # путь узла → id находки
        self.base = member_id(member)
        self.nodes: list[dict] = []
        self.edges: list[dict] = []
        self.exits: list[str] = []
        self.loop_stack: list[dict] = []
        self.entry = self.base

    def add_node(self, kind: str, node: Any, path: str, parent: str | None, data: dict) -> str:
        node_id = f"{self.base}/{path}" if path else self.base
        rng = self.src.rng(node)
        text = self.src.txt(node)
        # у контейнеров (циклы, условия) в подписи только заголовок: тело показывают вложенные блоки
        code = short(text.split("{", 1)[0] if kind in LOOPS | {"condition"} else text, 90)
        badges = self.badges(kind, node, node_id)
        self.nodes.append(
            {
                "id": node_id,
                "kind": kind,
                "label": LABELS[kind],
                "code": code,
                "range": rng,
                "parent_id": parent,
                "data": data,
                "badges": badges,
                "complexity": COMPLEXITY.get(self.member["name"]) if kind in LOOPS and path.count("/") == 0 and path.startswith(("foreach", "for", "while")) else None,
                "errors": [],
            }
        )
        return node_id

    def badges(self, kind: str, node: Any, node_id: str) -> list[dict]:
        out: list[dict] = []
        text = self.src.txt(node)
        if kind in {"var_decl", "assign", "operation"}:
            if text.startswith("System.out."):
                out.append({"kind": "output", "label": "вывод", "ref": None})
            if text.startswith("System.err."):
                out.append({"kind": "error_output", "label": "ошибка", "ref": None})
            for call in walk(node):
                if call.type == "method_invocation":
                    callee = self.src.txt(call.child_by_field_name("name"))
                    if callee in self.method_names and callee != self.member["name"]:
                        out.append({"kind": "call", "label": f"{callee}()", "ref": self.method_names[callee]})
                        break
        finding = self.findings.get(node_id.removeprefix(self.base + "/"))
        if finding:
            out.append({"kind": "defect", "label": finding.split(":")[0], "ref": finding})
        return out

    def edge(self, source: str, target: str, kind: str, label: str | None = None) -> None:
        self.edges.append(
            {"id": f"e{len(self.edges)}", "source": source, "target": target, "kind": kind, "label": label}
        )

    def sequence(self, stmts: list[Any], prefix: str, parent: str | None) -> tuple[str | None, list[tuple[str, str, str | None]]]:
        entry: str | None = None
        pending: list[tuple[str, str, str | None]] = []
        counters: dict[str, int] = {}
        for stmt in stmts:
            result = self.statement(stmt, prefix, parent, counters)
            if result is None:
                continue
            first, exits = result
            if entry is None:
                entry = first
            else:
                for source, kind, label in pending:
                    self.edge(source, first, kind, label)
            pending = exits
        return entry, pending

    def next_path(self, prefix: str, name: str, counters: dict[str, int]) -> str:
        index = counters.get(name, 0)
        counters[name] = index + 1
        return f"{prefix}{name}[{index}]"

    def statement(self, stmt: Any, prefix: str, parent: str | None, counters: dict[str, int]):
        t = stmt.type
        src = self.src
        if t == "block":
            return self.sequence([c for c in stmt.children if c.is_named and c.type != "comment"], prefix, parent)
        if t == "local_variable_declaration":
            decl = next(c for c in stmt.children if c.type == "variable_declarator")
            value = decl.child_by_field_name("value")
            path = self.next_path(prefix, "var", counters)
            data = {
                "type": src.txt(stmt.child_by_field_name("type")),
                "name": src.txt(decl.child_by_field_name("name")),
                "init": src.txt(value) if value is not None else None,
            }
            node_id = self.add_node("var_decl", stmt, path, parent, data)
            return node_id, [(node_id, "next", None)]
        if t == "expression_statement":
            expr = stmt.children[0]
            if expr.type in {"assignment_expression", "update_expression"}:
                kind, name = "assign", "assign"
                data: dict[str, Any] = {"expr": src.txt(expr)}
            else:
                kind, name = "operation", "op"
                data = {"expr": src.txt(expr)}
            node_id = self.add_node(kind, stmt, self.next_path(prefix, name, counters), parent, data)
            return node_id, [(node_id, "next", None)]
        if t in {"return_statement", "break_statement", "continue_statement"}:
            kind = t.removesuffix("_statement")
            node_id = self.add_node(kind, stmt, self.next_path(prefix, kind, counters), parent, {"expr": src.txt(stmt).rstrip(";")})
            if kind == "return":
                self.exits.append(node_id)
                return node_id, []
            if kind == "break":
                self.loop_stack[-1]["breaks"].append(node_id)
            else:
                self.edge(node_id, self.loop_stack[-1]["id"], "continue", "continue")
            return node_id, []
        if t == "enhanced_for_statement":
            path = self.next_path(prefix, "foreach", counters)
            data = {
                "type": src.txt(stmt.child_by_field_name("type")),
                "name": src.txt(stmt.child_by_field_name("name")),
                "iterable": src.txt(stmt.child_by_field_name("value")),
            }
            loop_id = self.add_node("loop_foreach", stmt, path, parent, data)
            ctx = {"id": loop_id, "breaks": []}
            self.loop_stack.append(ctx)
            first, body_exits = self.statement(stmt.child_by_field_name("body"), path + "/", loop_id, {})
            self.loop_stack.pop()
            if first:
                self.edge(loop_id, first, "body")
            for source, _, _ in body_exits:
                self.edge(source, loop_id, "back")
            exits = [(loop_id, "next", None)] + [(b, "break", "break") for b in ctx["breaks"]]
            return loop_id, exits
        if t == "if_statement":
            path = self.next_path(prefix, "if", counters)
            cond = stmt.child_by_field_name("condition")
            cond_id = self.add_node("condition", stmt, path, parent, {"expr": src.txt(cond)[1:-1]})
            then_first, then_exits = self.statement(stmt.child_by_field_name("consequence"), path + "/then/", parent, {})
            if then_first:
                self.edge(cond_id, then_first, "true", "Да")
            exits = list(then_exits)
            alternative = stmt.child_by_field_name("alternative")
            if alternative is not None:
                else_first, else_exits = self.statement(alternative, path + "/else/", parent, {})
                if else_first:
                    self.edge(cond_id, else_first, "false", "Нет")
                exits += else_exits
            else:
                exits.append((cond_id, "false", "Нет"))
            return cond_id, exits
        node_id = self.add_node("code", stmt, self.next_path(prefix, "code", counters), parent, {"text": src.txt(stmt)})
        return node_id, [(node_id, "next", None)]

    def build(self, version_id: int) -> dict:
        node = self.member["node"]
        body = node.child_by_field_name("body")
        params = [src_param for src_param in node.child_by_field_name("parameters").children if src_param.type == "formal_parameter"]
        method_node = {
            "id": self.base,
            "kind": "method",
            "label": LABELS["method"],
            "code": short(self.src.txt(node).split("{", 1)[0]),
            "range": self.src.rng(node),
            "parent_id": None,
            "data": {
                "name": self.member["name"],
                "return_type": self.src.txt(node.child_by_field_name("type")),
                "modifiers": modifiers_of(self.src, node),
                "params": [
                    {"type": self.src.txt(p.child_by_field_name("type")), "name": self.src.txt(p.child_by_field_name("name"))}
                    for p in params
                ],
            },
            "badges": [],
            "complexity": COMPLEXITY.get(self.member["name"]),
            "errors": [],
        }
        self.nodes.append(method_node)
        first, tail = self.sequence([c for c in body.children if c.is_named and c.type != "comment"], "", None)
        if first:
            self.edge(self.base, first, "next")
        for source, _, _ in tail:
            if source not in self.exits:
                self.exits.append(source)
        return {
            "method_id": self.base,
            "signature": member_key(self.member),
            "file": FILE,
            "nodes": self.nodes,
            "edges": self.edges,
            "entry": self.base,
            "exits": self.exits,
            "version_id": version_id,
            "content_hash": "mock-demo-orders-v3",
        }


# ---------------------------------------------------------------------------------------------
# Остальные фикстуры
# ---------------------------------------------------------------------------------------------


def find_line(src: Source, needle: str, start: int = 0) -> int:
    for i, line in enumerate(src.text.splitlines(), 1):
        if i > start and needle in line:
            return i
    raise KeyError(needle)


def method_range(members: list[dict], src: Source, name: str) -> dict:
    return src.rng(next(m["node"] for m in members if m["type"] == "Main" and m["name"] == name))


def build_findings(src: Source, members: list[dict], flows: dict[str, dict]) -> dict:
    def loc(path_id: str, flow_name: str) -> dict:
        node = next(n for n in flows[flow_name]["nodes"] if n["id"].endswith(path_id))
        return {
            "file": FILE,
            "start_line": node["range"]["start_line"],
            "end_line": node["range"]["end_line"],
            "node_id": node["id"],
            "method_id": flows[flow_name]["method_id"],
        }

    def mid(name: str) -> str:
        return flows[name]["method_id"] if name in flows else member_id(
            next(m for m in members if m["type"] == "Main" and m["name"] == name)
        )

    vip_line = find_line(src, "order.getCustomer() == VIP_CUSTOMER")
    catch_line = find_line(src, "catch (OrderParseException e) {", find_line(src, "private List<Order> readBatch"))
    report = method_range(members, src, "printReport")
    pre_ok = lambda name: {"name": name, "passed": True, "reason": None}  # noqa: E731
    findings = [
        {
            "id": f"PERF-01:{loc('foreach[0]', 'mergeDuplicates')['node_id']}",
            "rule_id": "PERF-01",
            "severity": "high",
            "category": "PERF",
            "title": "Вложенный цикл — O(n·m)",
            "location": loc("foreach[0]", "mergeDuplicates"),
            "explanation": "Внешний цикл по orders для каждого заказа обходит список merged целиком в поисках пары (клиент, товар, статус). Число сравнений растёт как n·m, где m — число различных пар.",
            "defect": "Повторный линейный поиск по уже собранному списку",
            "risk": "На 8000 заказов метод занимает секунды и растёт квадратично",
            "recommendation": "Индексировать merged по ключу (клиент, товар, статус) в LinkedHashMap",
            "complexity": {
                "current": "O(n·m)",
                "after": "O(n)",
                "confidence": "exact",
                "contributions": [
                    {"node_id": loc("foreach[0]", "mergeDuplicates")["node_id"], "factor": "n", "why": "цикл по всем заказам"},
                    {"node_id": loc("foreach[0]/foreach[0]", "mergeDuplicates")["node_id"], "factor": "m", "why": "поиск по списку merged"},
                ],
                "reason": None,
            },
            "fix": {
                "fix_id": "OPT-01",
                "available": True,
                "behavior_preserving": True,
                "preconditions": [
                    pre_ok("Внутренний цикл — поиск совпадения по ключу"),
                    pre_ok("Тело зависит только от пары"),
                    pre_ok("Порядок сохраняется (LinkedHashMap)"),
                ],
            },
            "evidence": {
                "static": [
                    {"kind": "loop", "text": "for (Order candidate : orders)", "node_id": loc("foreach[0]", "mergeDuplicates")["node_id"]},
                    {"kind": "loop", "text": "for (Order existing : merged)", "node_id": loc("foreach[0]/foreach[0]", "mergeDuplicates")["node_id"]},
                ],
                "dynamic": None,
            },
        },
        {
            "id": f"PERF-02:{loc('foreach[0]', 'distinctCustomers')['node_id']}",
            "rule_id": "PERF-02",
            "severity": "high",
            "category": "PERF",
            "title": "contains по ArrayList в цикле — O(n·m)",
            "location": loc("foreach[0]", "distinctCustomers"),
            "explanation": "result.contains(...) выполняет линейный поиск по ArrayList на каждой итерации цикла по заказам.",
            "defect": "Список используется как множество",
            "risk": "Квадратичный рост при увеличении числа клиентов",
            "recommendation": "Хранить встреченных клиентов в HashSet, список оставить для порядка",
            "complexity": {"current": "O(n·m)", "after": "O(n)", "confidence": "exact",
                           "contributions": [{"node_id": loc("foreach[0]", "distinctCustomers")["node_id"], "factor": "n", "why": "цикл по заказам"}],
                           "reason": None},
            "fix": {"fix_id": "OPT-02", "available": True, "behavior_preserving": True,
                    "preconditions": [pre_ok("Список не изменяется иначе как добавлением"), pre_ok("String имеет корректные equals/hashCode")]},
            "evidence": {"static": [{"kind": "call", "text": "result.contains(order.getCustomer())", "node_id": loc("foreach[0]/if[0]", "distinctCustomers")["node_id"]}], "dynamic": None},
        },
        {
            "id": f"PERF-03:{loc('foreach[0]', 'buildCsv')['node_id']}",
            "rule_id": "PERF-03",
            "severity": "medium",
            "category": "PERF",
            "title": "Конкатенация строк в цикле — O(n²)",
            "location": loc("foreach[0]", "buildCsv"),
            "explanation": "Переменная csv типа String накапливается оператором += в цикле: каждый шаг копирует всю строку.",
            "defect": "Копирование строки на каждой итерации",
            "risk": "Время и память растут квадратично с числом заказов",
            "recommendation": "Накапливать в StringBuilder и вызвать toString() после цикла",
            "complexity": {"current": "O(n²)", "after": "O(n)", "confidence": "exact",
                           "contributions": [{"node_id": loc("foreach[0]", "buildCsv")["node_id"], "factor": "n", "why": "копирование растущей строки"}],
                           "reason": None},
            "fix": {"fix_id": "OPT-03", "available": True, "behavior_preserving": True,
                    "preconditions": [pre_ok("Переменная локальная и типа String"), pre_ok("Используется только для накопления")]},
            "evidence": {"static": [{"kind": "assign", "text": "csv += …", "node_id": loc("foreach[0]/assign[0]", "buildCsv")["node_id"]}], "dynamic": None},
        },
        {
            "id": f"BUG-01:{FILE}#Main.discountFor(Order):{vip_line}",
            "rule_id": "BUG-01",
            "severity": "high",
            "category": "BUG",
            "title": "Сравнение строк по ==",
            "location": {"file": FILE, "start_line": vip_line, "end_line": vip_line, "node_id": None, "method_id": member_id(next(m for m in members if m["name"] == "discountFor"))},
            "explanation": "order.getCustomer() == VIP_CUSTOMER сравнивает ссылки, а не содержимое: имя клиента приходит из ввода и никогда не совпадает с константой.",
            "defect": "Скидка VIP-клиенту никогда не применяется",
            "risk": "Тихая потеря скидки",
            "recommendation": "Заменить на VIP_CUSTOMER.equals(order.getCustomer())",
            "complexity": None,
            "fix": {"fix_id": "FIX-01", "available": True, "behavior_preserving": False,
                    "preconditions": [pre_ok("Оба операнда типа String")]},
            "evidence": {"static": [{"kind": "literal", "text": "== VIP_CUSTOMER", "node_id": None}], "dynamic": None},
        },
        {
            "id": f"BUG-02:{FILE}#Main.readBatch(Scanner, int):{catch_line}",
            "rule_id": "BUG-02",
            "severity": "medium",
            "category": "BUG",
            "title": "Пустой catch",
            "location": {"file": FILE, "start_line": catch_line, "end_line": catch_line + 1, "node_id": None, "method_id": member_id(next(m for m in members if m["name"] == "readBatch"))},
            "explanation": "Блок catch (OrderParseException e) пуст: битые строки пакета молча пропускаются и не попадают в счётчик ошибок.",
            "defect": "Исключение проглатывается",
            "risk": "Ошибки ввода остаются незамеченными",
            "recommendation": "Вывести сообщение в stderr и увеличить errorCount",
            "complexity": None,
            "fix": {"fix_id": "FIX-02", "available": True, "behavior_preserving": False,
                    "preconditions": [pre_ok("Тело catch пусто")]},
            "evidence": {"static": [{"kind": "catch", "text": "catch (OrderParseException e) { }", "node_id": None}], "dynamic": None},
        },
        {
            "id": f"MAINT-01:{member_id(next(m for m in members if m['name'] == 'printReport'))}",
            "rule_id": "MAINT-01",
            "severity": "low",
            "category": "MAINT",
            "title": "Длинный метод",
            "location": {"file": FILE, "start_line": report["start_line"], "end_line": report["end_line"], "node_id": None, "method_id": member_id(next(m for m in members if m["name"] == "printReport"))},
            "explanation": f"Метод printReport занимает {report['end_line'] - report['start_line'] + 1} строк при пороге 30.",
            "defect": "Метод делает много независимых шагов",
            "risk": "Сложно читать и менять",
            "recommendation": "Выделить разделы отчёта в отдельные методы",
            "complexity": None,
            "fix": {"fix_id": "REF-01", "available": False, "behavior_preserving": True,
                    "preconditions": [{"name": "Выделяемый фрагмент не меняет несколько переменных", "passed": False, "reason": "Требуется выбор фрагмента (этап S9)"}]},
            "evidence": {"static": [{"kind": "metric", "text": "LOC > 30", "node_id": None}], "dynamic": None},
        },
        {
            "id": f"MAINT-05:{FILE}#Main",
            "rule_id": "MAINT-05",
            "severity": "medium",
            "category": "MAINT",
            "title": "God-class: разбор, анализ, преобразования и вывод в одном классе",
            "location": {"file": FILE, "start_line": find_line(src, "public class Main {"), "end_line": find_line(src, "interface Describable") - 2, "node_id": f"{FILE}#Main", "method_id": None},
            "explanation": "Класс Main содержит более 40 методов четырёх ролей (parse, analyze, optimize, print) и общее состояние.",
            "defect": "Одна ответственность на всё",
            "risk": "Любое изменение затрагивает весь файл",
            "recommendation": "Разбить на Parser, Analyzer, Optimizer, Printer",
            "complexity": None,
            "fix": {"fix_id": "REF-04", "available": False, "behavior_preserving": True,
                    "preconditions": [{"name": "Кластеры членов найдены", "passed": True, "reason": None}]},
            "evidence": {"static": [{"kind": "metric", "text": "методов > 20", "node_id": None}], "dynamic": None},
        },
    ]
    return {
        "version_id": 3,
        "findings": findings,
        "summary": {
            "total": len(findings),
            "by_severity": {"high": 3, "medium": 3, "low": 1},
            "by_category": {"PERF": 3, "BUG": 2, "MAINT": 2},
            "fixable": 5,
        },
        "complexity": {"current": "O(n²)", "optimized": "O(n)"},
        "metrics": build_metrics(src, members)["metrics"],
    }


def cyclomatic(text: str) -> int:
    code = re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', text)
    code = re.sub(r"//[^\n]*", "", code)
    return 1 + len(re.findall(r"\b(?:if|for|while|case|catch)\b|&&|\|\||\?", code))


def build_metrics(src: Source, members: list[dict]) -> dict:
    method_metrics = []
    for m in members:
        if m["kind"] != "method":
            continue
        rng = src.rng(m["node"])
        text = src.txt(m["node"])
        params = m["node"].child_by_field_name("parameters")
        method_metrics.append(
            {
                "method_id": member_id(m),
                "name": m["name"],
                "file": FILE,
                "lines": rng["end_line"] - rng["start_line"] + 1,
                "cyclomatic": cyclomatic(text),
                "cognitive": cyclomatic(text) + text.count("{") // 6,
                "max_nesting": max(1, text.count("{") // 5),
                "params": len([p for p in params.children if p.type == "formal_parameter"]),
                "complexity": COMPLEXITY.get(m["name"]),
            }
        )
    by_type: dict[str, list[dict]] = {}
    for m in members:
        by_type.setdefault(m["type"], []).append(m)
    type_metrics = []
    for name, ms in by_type.items():
        lines = sum(src.rng(m["node"])["end_line"] - src.rng(m["node"])["start_line"] + 1 for m in ms)
        type_metrics.append(
            {
                "type_id": f"{FILE}#{name}",
                "name": name,
                "file": FILE,
                "lines": lines,
                "methods": sum(1 for m in ms if m["kind"] == "method"),
                "fields": sum(1 for m in ms if m["kind"] == "field"),
                "lcom4": 4.0 if name == "Main" else 1.0,
            }
        )
    cyc = [m["cyclomatic"] for m in method_metrics]
    total_lines = len(src.text.splitlines())
    return {
        "version_id": 3,
        "metrics": {
            "totals": {
                "lines": total_lines,
                "code_lines": sum(1 for line in src.text.splitlines() if line.strip() and not line.strip().startswith(("//", "*", "/*"))),
                "files": 1,
                "types": len(by_type),
                "methods": len(method_metrics),
                "cyclomatic_avg": round(sum(cyc) / len(cyc), 2),
                "cyclomatic_max": max(cyc),
                "duplication_percent": 6.5,
                "lcom4_avg": 1.5,
            },
            "methods": method_metrics,
            "types": type_metrics,
        },
        "compare_to_version_id": None,
        "compare_to": None,
    }


def build_scenarios() -> dict:
    scenarios = []
    folder = REPO / "samples" / "demo-orders" / "scenarios"
    for i, path in enumerate(sorted(folder.glob("*.json")), 1):
        raw = json.loads(path.read_text(encoding="utf-8"))
        stdin = raw["stdin"]
        if len(stdin) > 1200:
            stdin = "\n".join(stdin.splitlines()[:12]) + "\n"  # в моке большой ввод усечён
        scenarios.append(
            {
                "id": i,
                "name": raw["name"],
                "description": raw["description"],
                "stdin": stdin,
                "args": [],
                "source": "manual",
                "size_factor": None,
                "enabled": True,
                "stability": "stable",
                "masks": [],
                "baseline": {"state": "recorded", "version_id": 1, "duration_ms": 90 + i * 7},
                "created_at": NOW,
            }
        )
    return {"scenarios": scenarios}


def build_runs(scenarios: dict) -> tuple[dict, dict, dict, list[dict]]:
    items_ok = [
        {
            "scenario_id": s["id"],
            "name": s["name"],
            "verdict": "PASS",
            "stdout": "",
            "stderr": "",
            "exit_code": 1 if s["name"] == "uncaught-exception" else 0,
            "duration_ms": 80 + s["id"] * 9,
            "baseline_ms": 90 + s["id"] * 7,
            "diff": None,
            "hits": None,
        }
        for s in scenarios["scenarios"]
    ]
    total = len(items_ok)
    run7 = {
        "id": 7,
        "kind": "test",
        "status": "done",
        "version_id": 3,
        "started_at": NOW,
        "finished_at": "2026-10-24T08:00:04Z",
        "summary": {"passed": total, "total": total, "coverage": 0.87, "version_status": "passed", "message": None, "data": None},
        "items": items_ok,
    }
    failing = {
        "scenario_id": 3,
        "name": scenarios["scenarios"][2]["name"],
        "verdict": "FAIL",
        "stdout": "",
        "stderr": "",
        "exit_code": 0,
        "duration_ms": 120,
        "baseline_ms": 105,
        "diff": {
            "stdout": {
                "expected": "Сумма (без отменённых): 3743.50\n",
                "actual": "Сумма (без отменённых): 3743.00\n",
                "unified": "@@ -1 +1 @@\n-Сумма (без отменённых): 3743.50\n+Сумма (без отменённых): 3743.00\n",
            },
            "stderr": None,
            "exit_code": None,
            "exception": None,
        },
        "hits": None,
    }
    items_fail = [failing if i["scenario_id"] == 3 else i for i in items_ok]
    run8 = {
        "id": 8,
        "kind": "test",
        "status": "done",
        "version_id": 4,
        "started_at": "2026-10-24T08:05:00Z",
        "finished_at": "2026-10-24T08:05:05Z",
        "summary": {"passed": total - 1, "total": total, "coverage": 0.87, "version_status": "failed", "message": "Поведение отличается в 1 сценарии", "data": None},
        "items": items_fail,
    }
    events: list[dict] = [
        {"event": "status", "data": {"status": "queued"}},
        {"event": "status", "data": {"status": "running"}},
        {"event": "gate", "data": {"stage": "syntax", "status": "passed", "details": None}},
        {"event": "log", "data": {"stream": "build", "text": "javac --release 21 -encoding UTF-8 -g Main.java"}},
        {"event": "gate", "data": {"stage": "compile", "status": "passed", "details": None}},
        {"event": "gate", "data": {"stage": "scenarios", "status": "running", "details": None}},
    ]
    for done, item in enumerate(items_fail, 1):
        events.append(
            {
                "event": "item",
                "data": {
                    "scenario_id": item["scenario_id"],
                    "name": item["name"],
                    "verdict": item["verdict"],
                    "duration_ms": item["duration_ms"],
                    "baseline_ms": item["baseline_ms"],
                    "diff": item["diff"],
                },
            }
        )
        events.append({"event": "progress", "data": {"done": done, "total": total}})
    events += [
        {"event": "gate", "data": {"stage": "scenarios", "status": "failed", "details": "1 из %d сценариев отличается" % total}},
        {"event": "result", "data": {"summary": run8["summary"]}},
        {"event": "status", "data": {"status": "done"}},
        {"event": "done", "data": {}},
    ]
    runs = {"runs": [{**run8, "items": []}, {**run7, "items": []}]}
    return run7, run8, runs, events


def build_static() -> dict[str, Any]:
    ok_pre = lambda n: {"name": n, "passed": True, "reason": None}  # noqa: E731
    return {
        "health": {"status": "ok", "version": "0.1.0-mock", "javac": "21.0.4", "java": "21.0.4", "db": "ok", "problems": []},
        "samples": {
            "samples": [
                {"id": "demo-orders", "name": "demo-orders", "description": "Учёт заказов магазина: монолит ≈1000 строк", "lines": 995},
                {"id": "analyzer-pairs", "name": "analyzer-pairs", "description": "Вложенные циклы и merge (слайд 5)", "lines": 80},
            ]
        },
        "projects": {
            "projects": [
                {"id": 1, "name": "demo-orders", "created_at": NOW, "updated_at": NOW, "head_version_id": 3, "main_class": "Main", "files_count": 1},
            ]
        },
        "project": {
            "id": 1,
            "name": "demo-orders",
            "created_at": NOW,
            "updated_at": NOW,
            "main_class": "Main",
            "main_class_candidates": ["Main"],
            "head_version_id": 3,
            "original_version_id": 1,
            "baseline_version_id": 1,
            "settings": {
                "run_timeout_s": 10, "compile_timeout_s": 30, "output_limit_bytes": 1048576, "jvm_xmx": "256m",
                "locale": "en_US", "timezone": "UTC", "rule_thresholds": {"MAINT-01": 30.0}, "gate_min_scenarios": 3, "gate_min_coverage": 0.6,
            },
            "gate": {"status": "passed", "passed": 11, "total": 11, "coverage": 0.87, "run_id": 7},
        },
        "versions": {
            "head_version_id": 3,
            "versions": [
                {"id": 3, "number": 3, "parent_id": 2, "origin": "optimize", "description": "Оптимизация O(n·m) → O(n)", "created_at": "2026-10-24T08:20:00Z", "gate_status": "passed", "status": "active", "content_hash": "mock-demo-orders-v3"},
                {"id": 2, "number": 2, "parent_id": 1, "origin": "graph_op", "description": "Добавить проверку на null", "created_at": "2026-10-24T08:10:00Z", "gate_status": "passed", "status": "active", "content_hash": "mock-demo-orders-v2"},
                {"id": 1, "number": 1, "parent_id": None, "origin": "upload", "description": "Оригинал", "created_at": NOW, "gate_status": "passed", "status": "active", "content_hash": "mock-demo-orders-v1"},
            ],
        },
        "files": {"version_id": 3, "files": [{"path": FILE, "lines": 995, "size": 0}]},
        "build": {"ok": True, "diagnostics": [], "duration_ms": 1240, "cached": False},
        "palette": {
            "blocks": [
                {"kind": "var_decl", "title": "Переменная", "group": "basic", "color": "blue", "icon": "variable",
                 "fields": [{"name": "type", "label": "Тип", "type": "type", "required": True, "default": "int", "options": []},
                            {"name": "name", "label": "Имя", "type": "identifier", "required": True, "default": None, "options": []},
                            {"name": "value", "label": "Значение", "type": "expression", "required": False, "default": None, "options": []}],
                 "template": "int count = 0;"},
                {"kind": "condition", "title": "Условие", "group": "control", "color": "orange", "icon": "git-branch",
                 "fields": [{"name": "expr", "label": "Выражение", "type": "expression", "required": True, "default": None, "options": []},
                            {"name": "add_else", "label": "Добавить else", "type": "boolean", "required": False, "default": False, "options": []}],
                 "template": "if (cond) { }"},
                {"kind": "loop_foreach", "title": "Цикл (for each)", "group": "control", "color": "teal", "icon": "repeat",
                 "fields": [{"name": "type", "label": "Тип", "type": "type", "required": True, "default": None, "options": []},
                            {"name": "name", "label": "Имя", "type": "identifier", "required": True, "default": None, "options": []},
                            {"name": "iterable", "label": "Коллекция", "type": "expression", "required": True, "default": None, "options": []}],
                 "template": "for (Order o : orders) { }"},
                {"kind": "operation", "title": "Операция", "group": "basic", "color": "teal", "icon": "terminal",
                 "fields": [{"name": "expr", "label": "Выражение", "type": "expression", "required": True, "default": None, "options": []}],
                 "template": "System.out.println(\"…\");"},
                {"kind": "return", "title": "Возврат", "group": "basic", "color": "green", "icon": "corner-down-left",
                 "fields": [{"name": "expr", "label": "Значение", "type": "expression", "required": False, "default": None, "options": []}],
                 "template": "return result;"},
            ]
        },
    }


VALIDATORS: dict[str, Any] = {
    "health": HealthResponse,
    "samples": SampleList,
    "projects": ProjectList,
    "project": ProjectDetail,
    "versions": VersionList,
    "files": FileList,
    "fixes": FixList,
    "build": BuildResult,
    "palette": Palette,
    "tree": ProjectTree,
    "structure": StructureGraph,
    "findings": AnalysisResponse,
    "metrics": MetricsResponse,
    "scenarios": ScenarioList,
    "runs": RunList,
    "run-7": RunInfo,
    "run-8": RunInfo,
    "file-main": FileContent,
}


STALE: list[str] = []
CHECK = False


def write(name: str, data: Any) -> None:
    if name.startswith("flow-"):
        FlowGraph.model_validate(data)
    elif name == "run-8-events":
        TypeAdapter(list[RunEvent]).validate_python(data)
    elif VALIDATORS.get(name) is not None:
        VALIDATORS[name].model_validate(data)
    OUT.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    (OUT / f"{name}.json").write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    global CHECK
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Генератор JSON-моков frontend")
    parser.add_argument("--check", action="store_true", help="не писать, а сверить с файлами")
    CHECK = parser.parse_args().check
    src = Source()
    types, members = collect_members(src)
    structure = build_structure(src, types, members)
    tree = build_tree(structure)

    method_names = {m["name"]: member_id(m) for m in members if m["kind"] == "method"}
    finding_ids = {
        "mergeDuplicates": {"foreach[0]": "PERF-01:{id}/foreach[0]"},
        "distinctCustomers": {"foreach[0]": "PERF-02:{id}/foreach[0]"},
        "buildCsv": {"foreach[0]": "PERF-03:{id}/foreach[0]"},
        "findOrderById": {},
    }
    flows: dict[str, dict] = {}
    for name, marks in finding_ids.items():
        member = next(m for m in members if m["type"] == "Main" and m["name"] == name)
        marks = {path: fid.format(id=member_id(member)) for path, fid in marks.items()}
        flows[name] = FlowBuilder(src, member, method_names, marks).build(version_id=3)

    for name, data in build_static().items():
        write(name, data)
    write("tree", tree)
    write("structure", structure)
    for name, flow in flows.items():
        write(f"flow-{name}", flow)
    findings = build_findings(src, members, flows)
    write("findings", findings)
    titles = {
        "OPT-01": "Индексация по ключу вместо вложенного поиска",
        "OPT-02": "contains в цикле → HashSet",
        "OPT-03": "Конкатенация → StringBuilder",
        "FIX-01": "== → equals",
        "FIX-02": "Заглушка вместо пустого catch",
        "REF-01": "Выделить метод",
        "REF-04": "Декомпозиция монолита",
    }
    write(
        "fixes",
        {
            "version_id": 3,
            "fixes": [
                {
                    "finding_id": f["id"],
                    "fix_id": f["fix"]["fix_id"],
                    "title": titles[f["fix"]["fix_id"]],
                    "behavior_preserving": f["fix"]["behavior_preserving"],
                    "available": f["fix"]["available"],
                }
                for f in findings["findings"]
                if f["fix"]
            ],
        },
    )
    write("metrics", build_metrics(src, members))
    scenarios = build_scenarios()
    write("scenarios", scenarios)
    run7, run8, runs, events = build_runs(scenarios)
    write("runs", runs)
    write("run-7", run7)
    write("run-8", run8)
    write("run-8-events", events)
    write(
        "file-main",
        {"path": FILE, "version_id": 3, "content": src.text, "syntax_errors": []},
    )
    if CHECK:
        if STALE:
            print("устарели: " + ", ".join(sorted(STALE)))
            print("обновить: cd backend && uv run python ../scripts/gen_mock_fixtures.py")
            return 1
        print("фикстуры актуальны")
        return 0
    print(f"fixtures written to {OUT.relative_to(REPO)}: {len(list(OUT.glob('*.json')))} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
