"""Блок-схема метода, конструктора или инициализатора (S2.5, S2.7).

Строится детерминированно из CST и лёгкой семантики. Любой оператор получает блок: то, что не
распознано, попадает в запасной блок ``code``, поэтому ни одна строка не теряется (инвариант I3).
Вложенные тела лямбд, анонимные и локальные типы показываются карточками внутри блока-хозяина.

Рёбра: ``next``, ``true``/``false`` (Да/Нет), ``case``, ``body``, ``back``, ``break``, ``continue``,
``exception`` (пунктир), ``call`` (к схеме вызываемого метода: ``target`` — id метода).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from tree_sitter import Node

from engine.graph.ids import PATH_NAMES, PathScope
from engine.graph.model import ApiRange, Badge, FlowEdge, FlowGraph, FlowNode
from engine.java import cst
from engine.java.semantic import Context
from engine.java.symbols import Member, base_name
from engine.java.ts import ParsedFile

Exit = tuple[str, str, str | None]  # (узел-источник, вид ребра, подпись)

LABELS = {
    "method": "Метод",
    "var_decl": "Переменная",
    "assign": "Присваивание",
    "operation": "Операция",
    "condition": "Условие",
    "switch": "Выбор",
    "case": "Ветка",
    "loop_for": "Цикл (for)",
    "loop_foreach": "Цикл (for each)",
    "loop_while": "Цикл (while)",
    "try": "Try",
    "catch": "Catch",
    "finally": "Finally",
    "throw": "Исключение",
    "return": "Возврат",
    "break": "Прервать",
    "continue": "Продолжить",
    "yield": "Yield",
    "lambda": "Лямбда",
    "local_type": "Локальный тип",
    "labeled": "Метка",
    "assert": "Код",
    "sync": "Код",
    "code": "Код",
}
MEMBER_LABELS = {"method": "Метод", "constructor": "Конструктор", "initializer": "Инициализатор"}

_OUTPUT_METHODS = {"print", "println", "printf", "format", "write", "append", "flush"}
_INPUT_METHODS = {
    "next",
    "nextInt",
    "nextLong",
    "nextDouble",
    "nextFloat",
    "nextBoolean",
    "nextLine",
    "hasNext",
    "hasNextInt",
    "hasNextLong",
    "hasNextDouble",
    "hasNextLine",
    "readLine",
    "read",
    "lines",
}
_INPUT_TYPES = {"Scanner", "BufferedReader", "InputStreamReader", "Console", "InputStream"}
_STREAM_ROOTS = {"IntStream", "LongStream", "DoubleStream", "Stream", "Arrays", "Collectors"}
_STREAM_OPS = {
    "stream",
    "parallelStream",
    "filter",
    "map",
    "mapToInt",
    "mapToLong",
    "mapToDouble",
    "mapToObj",
    "boxed",
    "flatMap",
    "sorted",
    "distinct",
    "limit",
    "skip",
    "peek",
    "forEach",
    "reduce",
    "collect",
    "count",
    "sum",
    "min",
    "max",
    "average",
    "anyMatch",
    "allMatch",
    "noneMatch",
    "findFirst",
    "findAny",
    "toList",
    "toArray",
    "range",
    "rangeClosed",
    "iterate",
    "generate",
}
_TRANSPARENT = {"block", ";", "empty_statement"}
_DECLARATIONS = cst.TYPE_DECLARATIONS


@dataclass(slots=True)
class _Jump:
    """Цель break/continue: цикл, switch или помеченный оператор."""

    kind: str  # loop | switch | label
    node_id: str
    label: str | None
    breaks: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _Handler:
    """Catch-секции открытого try (для рёбер ``exception`` от ``throw``)."""

    catches: list[tuple[str, tuple[str, ...]]]


class FlowBuilder:
    def __init__(
        self,
        parsed: ParsedFile,
        file: str,
        member: Member,
        declaration: Node,
        ctx: Context,
        content_hash: str = "",
    ) -> None:
        self.parsed = parsed
        self.file = file
        self.member = member
        self.declaration = declaration
        self.ctx = ctx
        self.content_hash = content_hash
        self.base = member.id
        self.nodes: list[FlowNode] = []
        self.edges: list[FlowEdge] = []
        self.exits: list[str] = []
        self.jumps: list[_Jump] = []
        self.handlers: list[_Handler] = []
        self._call_edges: set[tuple[str, str]] = set()

    # --- служебное ---------------------------------------------------------------------------

    def rng(self, node: Node) -> ApiRange:
        return ApiRange.of(self.file, self.parsed.range_of(node))

    def text(self, node: Node | None) -> str:
        return cst.text_of(self.parsed, node)

    def edge(self, source: str, target: str, kind: str, label: str | None = None) -> None:
        self.edges.append(FlowEdge(f"e{len(self.edges)}", source, target, kind, label))

    def add_node(
        self,
        kind: str,
        node: Node,
        scope: PathScope,
        parent: str | None,
        data: dict[str, Any],
        code: str | None = None,
        segment: str | None = None,
    ) -> FlowNode:
        path = segment if segment is not None else scope.next(PATH_NAMES[kind])
        full = f"{self.base}/{path}"
        flow_node = FlowNode(
            id=full,
            kind=kind,
            label=LABELS[kind],
            code=cst.short(code if code is not None else self.text(node)),
            range=self.rng(node),
            parent_id=parent,
            data=dict(data),
        )
        self.nodes.append(flow_node)
        return flow_node

    @staticmethod
    def path_of(flow_node: FlowNode, base: str) -> str:
        return flow_node.id[len(base) + 1 :]

    def header(self, node: Node, stop: Node | None) -> str:
        end = stop.start_byte if stop is not None else node.end_byte
        return self.parsed.source[node.start_byte : end].decode("utf-8", errors="replace")

    def expr_text(self, node: Node | None) -> str:
        """Текст выражения без внешних скобок ``parenthesized_expression``."""
        if node is not None and node.type == "parenthesized_expression":
            inner = cst.named_children(node)
            return cst.squash(self.text(inner[0])) if inner else ""
        return cst.squash(self.text(node))

    # --- вход ------------------------------------------------------------------------------------

    def build(self) -> FlowGraph:
        member = self.member
        decl = self.declaration
        body = decl.child_by_field_name("body")
        if body is None and decl.type == "static_initializer":
            body = cst.first_child_of_type(decl, "block")
        if body is None and decl.type == "block":
            body = decl
        header = " ".join(
            part
            for part in (
                " ".join(member.modifiers),
                " ".join(member.type_params),
                member.type_text or "",
                member.key,
            )
            if part
        )
        root = FlowNode(
            id=self.base,
            kind="method",
            label=MEMBER_LABELS.get(member.kind, "Метод"),
            code=cst.short(header),
            range=self.rng(decl),
            data={
                "name": member.name,
                "member_kind": member.kind,
                "return_type": member.type_text,
                "modifiers": list(member.modifiers),
                "params": [{"type": p.type, "name": p.name} for p in member.params],
                "throws": list(member.throws),
                "type_params": list(member.type_params),
                "has_body": body is not None,
            },
        )
        self.nodes.append(root)
        tail: list[Exit] = []
        if body is not None:
            statements = cst.named_children(body)
            entry, tail = self.sequence(statements, PathScope(), None)
            if entry is not None:
                self.edge(self.base, entry, "next")
            else:
                tail = [(self.base, "next", None)]
        else:
            tail = [(self.base, "next", None)]
        for source, _, _ in tail:
            if source not in self.exits:
                self.exits.append(source)
        return FlowGraph(
            method_id=self.base,
            signature=member.key,
            file=self.file,
            nodes=self.nodes,
            edges=self.edges,
            entry=self.base,
            exits=self.exits,
            content_hash=self.content_hash,
        )

    # --- последовательности --------------------------------------------------------------------

    def flatten(self, statements: Iterable[Node]) -> list[Node]:
        """Раскрывает вложенные ``{ … }`` и убирает пустые операторы и комментарии."""
        flat: list[Node] = []
        for stmt in statements:
            if stmt.type in cst.COMMENT_TYPES or stmt.type in _TRANSPARENT:
                if stmt.type == "block":
                    flat.extend(self.flatten(cst.named_children(stmt)))
                continue
            flat.append(stmt)
        return flat

    def sequence(
        self, statements: list[Node], scope: PathScope, parent: str | None
    ) -> tuple[str | None, list[Exit]]:
        entry: str | None = None
        pending: list[Exit] = []
        for stmt in self.flatten(statements):
            result = self.statement(stmt, scope, parent, None)
            first, exits = result
            if entry is None:
                entry = first
            else:
                for source, kind, label in pending:
                    self.edge(source, first, kind, label)
            pending = exits
        return entry, pending

    def statement(
        self, node: Node, scope: PathScope, parent: str | None, label: str | None
    ) -> tuple[str, list[Exit]]:
        kind = node.type
        if kind == "local_variable_declaration":
            return self.var_decl(node, scope, parent)
        if kind == "expression_statement":
            return self.expression(node, scope, parent)
        if kind == "explicit_constructor_invocation":
            return self.simple(
                "operation", node, scope, parent, {"expr": self.expr_text(node).rstrip(";")}, [node]
            )
        if kind == "if_statement":
            return self.if_statement(node, scope, parent)
        if kind in {"for_statement", "enhanced_for_statement", "while_statement", "do_statement"}:
            return self.loop(node, scope, parent, label)
        if kind == "switch_expression":
            return self.switch(node, scope, parent, label)
        if kind in {"try_statement", "try_with_resources_statement"}:
            return self.try_statement(node, scope, parent)
        if kind == "labeled_statement":
            return self.labeled(node, scope, parent)
        if kind == "return_statement":
            return self.terminal("return", node, scope, parent)
        if kind == "throw_statement":
            return self.throw(node, scope, parent)
        if kind == "yield_statement":
            return self.terminal("yield", node, scope, parent)
        if kind in {"break_statement", "continue_statement"}:
            return self.jump(node, scope, parent)
        if kind == "assert_statement":
            flow = self.add_node(
                "assert", node, scope, parent, {"expr": cst.squash(self.text(node)).rstrip(";")}
            )
            self.decorate(flow, cst.named_children(node))
            return flow.id, [(flow.id, "next", None)]
        if kind == "synchronized_statement":
            lock = cst.first_child_of_type(node, "parenthesized_expression")
            flow = self.add_node(
                "sync",
                node,
                scope,
                parent,
                {"expr": self.expr_text(lock)},
                code=self.header(node, node.child_by_field_name("body")),
            )
            return flow.id, [(flow.id, "next", None)]
        if kind in _DECLARATIONS:
            return self.local_type(node, scope, parent)
        flow = self.add_node("code", node, scope, parent, {"text": self.text(node), "cst": kind})
        return flow.id, [(flow.id, "next", None)]

    # --- простые операторы -------------------------------------------------------------------

    def simple(
        self,
        kind: str,
        node: Node,
        scope: PathScope,
        parent: str | None,
        data: dict[str, Any],
        expressions: list[Node],
    ) -> tuple[str, list[Exit]]:
        flow = self.add_node(kind, node, scope, parent, data)
        self.decorate(flow, expressions)
        return flow.id, [(flow.id, "next", None)]

    def var_decl(self, node: Node, scope: PathScope, parent: str | None) -> tuple[str, list[Exit]]:
        declarators = []
        for declarator in cst.children_of_type(node, "variable_declarator"):
            value = declarator.child_by_field_name("value")
            dims = cst.first_child_of_type(declarator, "dimensions")
            declarators.append(
                {
                    "name": self.text(declarator.child_by_field_name("name")),
                    "dims": cst.squash(self.text(dims)) if dims is not None else "",
                    "init": cst.squash(self.text(value)) if value is not None else None,
                }
            )
        mods, _ = cst.modifiers_of(self.parsed, node)
        data = {
            "type": cst.squash(self.text(node.child_by_field_name("type"))),
            "names": [d["name"] for d in declarators],
            "declarators": declarators,
            "modifiers": list(mods),
        }
        return self.simple("var_decl", node, scope, parent, data, [node])

    def expression(
        self, node: Node, scope: PathScope, parent: str | None
    ) -> tuple[str, list[Exit]]:
        named = cst.named_children(node)
        expr = named[0] if named else node
        text = cst.squash(self.text(expr))
        if expr.type == "assignment_expression":
            operator = cst.squash(self.text(expr.child_by_field_name("operator")))
            data: dict[str, object] = {
                "expr": text,
                "target": cst.squash(self.text(expr.child_by_field_name("left"))),
                "op": operator,
                "value": cst.squash(self.text(expr.child_by_field_name("right"))),
            }
            return self.simple("assign", node, scope, parent, data, [expr])
        if expr.type == "update_expression":
            operator = "++" if "++" in text else "--"
            target = text.replace("++", "").replace("--", "")
            return self.simple(
                "assign",
                node,
                scope,
                parent,
                {"expr": text, "target": target, "op": operator, "value": None},
                [expr],
            )
        return self.simple("operation", node, scope, parent, {"expr": text}, [expr])

    def terminal(
        self, kind: str, node: Node, scope: PathScope, parent: str | None
    ) -> tuple[str, list[Exit]]:
        named = cst.named_children(node)
        expr = named[0] if named else None
        flow = self.add_node(
            kind, node, scope, parent, {"expr": cst.squash(self.text(expr)) if expr else None}
        )
        self.decorate(flow, [expr] if expr is not None else [])
        if kind == "return":
            self.exits.append(flow.id)
        return flow.id, []

    def throw(self, node: Node, scope: PathScope, parent: str | None) -> tuple[str, list[Exit]]:
        named = cst.named_children(node)
        expr = named[0] if named else None
        thrown = ""
        if expr is not None and expr.type == "object_creation_expression":
            thrown = base_name(self.text(expr.child_by_field_name("type")))
        flow = self.add_node(
            "throw",
            node,
            scope,
            parent,
            {"expr": cst.squash(self.text(expr)) if expr else None, "type": thrown or None},
        )
        self.decorate(flow, [expr] if expr is not None else [])
        if thrown:
            flow.badges.append(Badge("exception", thrown))
        if not self.route_exception(flow.id, thrown):
            self.exits.append(flow.id)
        return flow.id, []

    def route_exception(self, source: str, thrown: str) -> bool:
        """Ребро ``exception`` в ближайший подходящий catch; ``False`` — исключение уходит из метода."""
        for handler in reversed(self.handlers):
            for catch_id, types in handler.catches:
                if self.catches(types, thrown):
                    self.edge(source, catch_id, "exception", thrown or None)
                    return True
        return False

    def catches(self, types: tuple[str, ...], thrown: str) -> bool:
        for caught in types:
            if not thrown:
                if caught in {"Exception", "Throwable"}:
                    return True
                continue
            if caught == thrown or caught in {"Exception", "Throwable"}:
                return True
            decl = self.ctx.table.type_named(thrown, self.ctx.owner)
            if decl is not None and any(p.name == caught for p in self.ctx.table.supertypes(decl)):
                return True
            if caught == "RuntimeException" and decl is None and thrown.endswith("Exception"):
                return thrown not in {"IOException", "InterruptedException", "SQLException"}
        return False

    def jump(self, node: Node, scope: PathScope, parent: str | None) -> tuple[str, list[Exit]]:
        is_break = node.type == "break_statement"
        label_node = cst.first_child_of_type(node, "identifier")
        label = self.text(label_node) if label_node is not None else None
        kind = "break" if is_break else "continue"
        flow = self.add_node(kind, node, scope, parent, {"label": label})
        target = self.find_jump(is_break, label)
        if target is None:
            return flow.id, [(flow.id, "next", None)]
        if is_break:
            target.breaks.append(flow.id)
        else:
            self.edge(flow.id, target.node_id, "continue", label or "continue")
        return flow.id, []

    def find_jump(self, is_break: bool, label: str | None) -> _Jump | None:
        for jump in reversed(self.jumps):
            if label is not None:
                if jump.label == label:
                    return jump
            elif jump.kind == "loop" or (is_break and jump.kind == "switch"):
                return jump
        return None

    # --- условия, циклы, выбор, try ---------------------------------------------------------

    def if_statement(
        self, node: Node, scope: PathScope, parent: str | None
    ) -> tuple[str, list[Exit]]:
        condition = node.child_by_field_name("condition")
        consequence = node.child_by_field_name("consequence")
        alternative = node.child_by_field_name("alternative")
        flow = self.add_node(
            "condition",
            node,
            scope,
            parent,
            {"expr": self.expr_text(condition)},
            code=self.header(node, consequence),
        )
        self.decorate(flow, [condition] if condition is not None else [])
        path = self.path_of(flow, self.base)
        exits: list[Exit] = []
        then_first, then_exits = (
            self.sequence([consequence], PathScope(prefix=f"{path}/then/"), parent)
            if consequence is not None
            else (None, [])
        )
        if then_first is not None:
            self.edge(flow.id, then_first, "true", "Да")
            exits.extend(then_exits)
        else:
            exits.append((flow.id, "true", "Да"))
        if alternative is not None:
            else_first, else_exits = self.sequence(
                [alternative], PathScope(prefix=f"{path}/else/"), parent
            )
            if else_first is not None:
                self.edge(flow.id, else_first, "false", "Нет")
                exits.extend(else_exits)
            else:
                exits.append((flow.id, "false", "Нет"))
        else:
            exits.append((flow.id, "false", "Нет"))
        return flow.id, exits

    def loop(
        self, node: Node, scope: PathScope, parent: str | None, label: str | None
    ) -> tuple[str, list[Exit]]:
        body = node.child_by_field_name("body")
        header_nodes: list[Node] = []
        data: dict[str, Any]
        if node.type == "for_statement":
            kind = "loop_for"
            init = node.children_by_field_name("init")
            update = node.children_by_field_name("update")
            condition = node.child_by_field_name("condition")
            data = {
                "init": [cst.squash(self.text(n)).rstrip(";") for n in init],
                "cond": cst.squash(self.text(condition)) if condition is not None else None,
                "update": [cst.squash(self.text(n)) for n in update],
            }
            header_nodes = [*init, *([condition] if condition is not None else []), *update]
        elif node.type == "enhanced_for_statement":
            kind = "loop_foreach"
            iterable = node.child_by_field_name("value")
            data = {
                "type": cst.squash(self.text(node.child_by_field_name("type"))),
                "name": self.text(node.child_by_field_name("name")),
                "iterable": cst.squash(self.text(iterable)),
            }
            header_nodes = [iterable] if iterable is not None else []
        else:
            kind = "loop_while"
            condition = node.child_by_field_name("condition")
            data = {"cond": self.expr_text(condition), "do_while": node.type == "do_statement"}
            header_nodes = [condition] if condition is not None else []
        code = self.header(node, body)
        if node.type == "do_statement":
            code = f"do … while {self.text(node.child_by_field_name('condition'))}"
        flow = self.add_node(kind, node, scope, parent, data, code=code)
        self.decorate(flow, header_nodes)
        jump = _Jump("loop", flow.id, label)
        self.jumps.append(jump)
        first, body_exits = (
            self.sequence([body], PathScope(prefix=f"{self.path_of(flow, self.base)}/"), flow.id)
            if body is not None
            else (None, [])
        )
        self.jumps.pop()
        if first is not None:
            self.edge(flow.id, first, "body")
        for source, _, exit_label in body_exits:
            self.edge(source, flow.id, "back", exit_label)
        exits: list[Exit] = [(flow.id, "next", None)]
        exits.extend((b, "break", "break") for b in jump.breaks)
        return flow.id, exits

    def labeled(self, node: Node, scope: PathScope, parent: str | None) -> tuple[str, list[Exit]]:
        label_node = cst.first_child_of_type(node, "identifier")
        label = self.text(label_node)
        inner = [c for c in cst.named_children(node) if c.type != "identifier"]
        flow = self.add_node("labeled", node, scope, parent, {"label": label}, code=f"{label}:")
        jump = _Jump("label", flow.id, label)
        self.jumps.append(jump)
        inner_scope = PathScope(prefix=f"{self.path_of(flow, self.base)}/")
        first: str | None = None
        exits: list[Exit] = []
        if inner:
            first, exits = self.statement(inner[0], inner_scope, flow.id, label)
        self.jumps.pop()
        if first is not None:
            self.edge(flow.id, first, "body")
        exits = [*exits, *((b, "break", f"break {label}") for b in jump.breaks)]
        return flow.id, exits

    def switch(
        self, node: Node, scope: PathScope, parent: str | None, label: str | None
    ) -> tuple[str, list[Exit]]:
        condition = node.child_by_field_name("condition")
        block = node.child_by_field_name("body")
        groups = cst.named_children(block) if block is not None else []
        style = "arrow" if groups and groups[0].type == "switch_rule" else "classic"
        flow = self.add_node(
            "switch",
            node,
            scope,
            parent,
            {"expr": self.expr_text(condition), "style": style},
            code=f"switch ({self.expr_text(condition)})",
        )
        self.decorate(flow, [condition] if condition is not None else [])
        path = self.path_of(flow, self.base)
        jump = _Jump("switch", flow.id, label)
        self.jumps.append(jump)
        case_scope = PathScope(prefix=f"{path}/")
        exits: list[Exit] = []
        fallthrough: list[Exit] = []
        has_default = False
        for group in groups:
            labels = [cst.squash(self.text(n)) for n in cst.children_of_type(group, "switch_label")]
            is_default = any(text.startswith("default") for text in labels)
            has_default = has_default or is_default
            shown = ", ".join(t.removeprefix("case ").strip() for t in labels) or "default"
            case = self.add_node(
                "case",
                group,
                case_scope,
                flow.id,
                {
                    "labels": [t.removeprefix("case ").strip() for t in labels],
                    "default": is_default,
                },
                code=" ".join(labels),
            )
            self.edge(flow.id, case.id, "case", shown)
            for source, kind, exit_label in fallthrough:
                self.edge(source, case.id, kind, "далее" if kind == "next" else exit_label)
            body = [c for c in cst.named_children(group) if c.type != "switch_label"]
            first, body_exits = self.sequence(
                body, PathScope(prefix=f"{self.path_of(case, self.base)}/"), case.id
            )
            if first is not None:
                self.edge(case.id, first, "body")
            else:
                body_exits = [(case.id, "next", None)]
            if style == "arrow":
                exits.extend(body_exits)
                fallthrough = []
            else:
                fallthrough = list(body_exits)
        self.jumps.pop()
        exits.extend(fallthrough)
        exits.extend((b, "break", "break") for b in jump.breaks)
        if not has_default:
            exits.append((flow.id, "next", "иначе"))
        return flow.id, exits

    def try_statement(
        self, node: Node, scope: PathScope, parent: str | None
    ) -> tuple[str, list[Exit]]:
        resources_node = cst.first_child_of_type(node, "resource_specification")
        resources: list[dict[str, str | None]] = []
        resource_values: list[Node] = []
        if resources_node is not None:
            for resource in cst.children_of_type(resources_node, "resource"):
                value = resource.child_by_field_name("value")
                resources.append(
                    {
                        "type": cst.squash(self.text(resource.child_by_field_name("type"))) or None,
                        "name": self.text(resource.child_by_field_name("name")) or None,
                        "init": cst.squash(self.text(value))
                        if value is not None
                        else cst.squash(self.text(resource)),
                    }
                )
                if value is not None:
                    resource_values.append(value)
        body = node.child_by_field_name("body")
        head = self.header(node, body)
        flow = self.add_node("try", node, scope, parent, {"resources": resources}, code=head)
        self.decorate(flow, resource_values)
        path = self.path_of(flow, self.base)

        catch_scope = PathScope(prefix=f"{path}/")
        catches: list[tuple[FlowNode, Node, tuple[str, ...]]] = []
        for clause in cst.children_of_type(node, "catch_clause"):
            parameter = cst.first_child_of_type(clause, "catch_formal_parameter")
            catch_type = (
                cst.first_child_of_type(parameter, "catch_type") if parameter is not None else None
            )
            types = (
                tuple(base_name(self.text(t)) for t in cst.named_children(catch_type))
                if catch_type
                else ()
            )
            name = self.text(parameter.child_by_field_name("name")) if parameter is not None else ""
            clause_body = clause.child_by_field_name("body")
            catch_node = self.add_node(
                "catch",
                clause,
                catch_scope,
                flow.id,
                {"types": list(types), "name": name},
                code=self.header(clause, clause_body),
            )
            catches.append((catch_node, clause, types))
        finally_clause = cst.first_child_of_type(node, "finally_clause")
        finally_node: FlowNode | None = None
        if finally_clause is not None:
            finally_node = self.add_node(
                "finally",
                finally_clause,
                catch_scope,
                flow.id,
                {},
                code="finally",
                segment=f"{path}/finally",
            )

        self.handlers.append(_Handler([(c.id, t) for c, _, t in catches]))
        first, body_exits = (
            self.sequence([body], PathScope(prefix=f"{path}/body/"), flow.id)
            if body is not None
            else (None, [])
        )
        self.handlers.pop()
        if first is not None:
            self.edge(flow.id, first, "body")
        exits: list[Exit] = list(body_exits)
        for catch_node, clause, types in catches:
            self.edge(flow.id, catch_node.id, "exception", " | ".join(types) or None)
            clause_body = clause.child_by_field_name("body")
            c_first, c_exits = (
                self.sequence(
                    [clause_body],
                    PathScope(prefix=f"{self.path_of(catch_node, self.base)}/"),
                    catch_node.id,
                )
                if clause_body is not None
                else (None, [])
            )
            if c_first is not None:
                self.edge(catch_node.id, c_first, "body")
                exits.extend(c_exits)
            else:
                exits.append((catch_node.id, "next", None))
        if finally_node is not None and finally_clause is not None:
            f_body = cst.first_child_of_type(finally_clause, "block")
            for source, kind, label in exits:
                self.edge(source, finally_node.id, kind, label)
            if not exits:
                self.edge(flow.id, finally_node.id, "next", "finally")
            f_first, f_exits = (
                self.sequence([f_body], PathScope(prefix=f"{path}/finally/"), finally_node.id)
                if f_body is not None
                else (None, [])
            )
            if f_first is not None:
                self.edge(finally_node.id, f_first, "body")
                return flow.id, f_exits
            return flow.id, [(finally_node.id, "next", None)]
        return flow.id, exits

    # --- локальные типы -------------------------------------------------------------------------

    def local_type(
        self, node: Node, scope: PathScope, parent: str | None
    ) -> tuple[str, list[Exit]]:
        name = self.text(node.child_by_field_name("name"))
        body = node.child_by_field_name("body")
        flow = self.add_node(
            "local_type",
            node,
            scope,
            parent,
            {
                "type_kind": node.type.removesuffix("_declaration"),
                "name": name,
                "members": self.member_names(body),
            },
            code=self.header(node, body),
        )
        return flow.id, [(flow.id, "next", None)]

    def member_names(self, body: Node | None) -> list[str]:
        if body is None:
            return []
        names: list[str] = []
        for child in cst.named_children(body):
            if child.type in {"method_declaration", "constructor_declaration"}:
                names.append(self.text(child.child_by_field_name("name")) + "()")
            elif child.type == "field_declaration":
                for declarator in cst.children_of_type(child, "variable_declarator"):
                    names.append(self.text(declarator.child_by_field_name("name")))
        return names

    # --- наложения: бейджи, вызовы, лямбды, анонимные типы, конвейеры -----------------------------

    def decorate(self, flow: FlowNode, expressions: list[Node]) -> None:
        """Бейджи ввода/вывода/вызова и вложенные карточки для выражений блока ``flow``."""
        lambdas: list[Node] = []
        anonymous: list[Node] = []
        switches: list[Node] = []
        chains: list[Node] = []
        seen_badges: set[tuple[str, str, str | None]] = set(
            (b.kind, b.label, b.ref) for b in flow.badges
        )

        def add_badge(kind: str, label: str, ref: str | None = None) -> None:
            key = (kind, label, ref)
            if key not in seen_badges:
                seen_badges.add(key)
                flow.badges.append(Badge(kind, label, ref))

        calls: list[str] = []
        stack = [e for e in reversed(expressions) if e is not None]
        while stack:
            current = stack.pop()
            kind = current.type
            if kind == "lambda_expression":
                lambdas.append(current)
                continue
            if kind == "switch_expression":
                switches.append(current)  # ветки и yield разворачиваются в карточку ниже
                continue
            if kind == "method_invocation":
                self.invocation(current, add_badge, calls)
                parent = current.parent
                outer_object = (
                    parent.child_by_field_name("object")
                    if parent is not None and parent.type == "method_invocation"
                    else None
                )
                is_inner = outer_object is not None and outer_object.id == current.id
                if not is_inner:
                    chains.append(current)
            elif kind == "object_creation_expression":
                for target in self.ctx.resolve_creation(current):
                    calls.append(target.id)
                    add_badge("call", f"new {target.name}", target.id)
                class_body = cst.first_child_of_type(current, "class_body")
                if class_body is not None:
                    anonymous.append(current)
                    arguments = current.child_by_field_name("arguments")
                    if arguments is not None:
                        stack.extend(reversed(arguments.children))
                    continue
            elif kind == "explicit_constructor_invocation":
                for target in self.ctx.resolve_explicit_constructor(current):
                    calls.append(target.id)
                    add_badge("call", f"{target.name}(…)", target.id)
            elif kind == "field_access" and self.text(current) == "System.in":
                add_badge("input", "ввод")
            stack.extend(reversed(current.children))

        for target_id in dict.fromkeys(calls):
            if (flow.id, target_id) not in self._call_edges:
                self._call_edges.add((flow.id, target_id))
                self.edge(flow.id, target_id, "call", None)
        if calls:
            flow.data["calls"] = list(dict.fromkeys(calls))
        pipelines = [p for p in (self.pipeline(c) for c in chains) if p]
        if pipelines:
            flow.data["pipelines"] = pipelines

        path = self.path_of(flow, self.base) if flow.id != self.base else ""
        host_scope = PathScope(prefix=f"{path}/" if path else "")
        for lam in lambdas:
            self.lambda_node(lam, flow, host_scope)
        for expression_switch in switches:
            self.embedded_switch(expression_switch, flow, host_scope)
        for creation in anonymous:
            body = cst.first_child_of_type(creation, "class_body")
            type_text = cst.squash(self.text(creation.child_by_field_name("type")))
            local = self.add_node(
                "local_type",
                creation,
                host_scope,
                flow.id,
                {
                    "type_kind": "anonymous",
                    "name": None,
                    "base": type_text,
                    "members": self.member_names(body),
                },
                code=f"new {type_text}() {{ … }}",
            )
            _ = local

    def invocation(
        self,
        call: Node,
        add_badge: Callable[..., None],
        calls: list[str],
    ) -> None:
        name = self.text(call.child_by_field_name("name"))
        target = call.child_by_field_name("object")
        target_text = cst.squash(self.text(target)) if target is not None else ""
        if target_text == "System.out" and name in _OUTPUT_METHODS:
            add_badge("output", "вывод")
        elif target_text == "System.err" and name in _OUTPUT_METHODS:
            add_badge("error_output", "ошибка")
        elif name in _INPUT_METHODS and target is not None:
            receiver = self.ctx.expr_type(target)
            if (receiver in _INPUT_TYPES) or target_text.startswith("System.in"):
                add_badge("input", "ввод")
        resolved = self.ctx.resolve_call(call)
        if resolved:
            shown = f"{name}()" if len(resolved) == 1 else f"{name}() ×{len(resolved)}"
            add_badge("call", shown, resolved[0].id)
            calls.extend(m.id for m in resolved)

    def pipeline(self, call: Node) -> list[dict[str, str]]:
        """Цепочка Stream: этапы в порядке выполнения (``stream → filter → map → collect``)."""
        stages: list[dict[str, str]] = []
        current: Node | None = call
        while current is not None and current.type == "method_invocation":
            arguments = current.child_by_field_name("arguments")
            stages.append(
                {
                    "name": self.text(current.child_by_field_name("name")),
                    "args": cst.short(self.text(arguments), 60) if arguments is not None else "()",
                }
            )
            current = current.child_by_field_name("object")
        root = cst.squash(self.text(current)) if current is not None else ""
        stages.reverse()
        names = {stage["name"] for stage in stages}
        starts = bool(names & {"stream", "parallelStream"}) or root in _STREAM_ROOTS
        return stages if starts and len(stages) >= 2 else []

    def embedded_switch(self, node: Node, host: FlowNode, host_scope: PathScope) -> None:
        """``switch`` внутри выражения (``int r = switch …``): контейнер-карточка внутри блока-хозяина.

        Рёбер между хозяином и веткой нет: ``break``/``continue`` не пересекают границу выражения,
        а ``throw`` по-прежнему уходит в охватывающий ``catch``.
        """
        saved = self.jumps
        self.jumps = []
        try:
            self.switch(node, host_scope, host.id, None)
        finally:
            self.jumps = saved

    def lambda_node(self, lam: Node, host: FlowNode, host_scope: PathScope) -> None:
        params_node = lam.child_by_field_name("parameters")
        body = lam.child_by_field_name("body")
        params: list[str] = []
        if params_node is not None:
            if params_node.type == "identifier":
                params = [self.text(params_node)]
            else:
                for item in params_node.children:
                    if item.type == "formal_parameter":
                        params.append(self.text(item.child_by_field_name("name")))
                    elif item.type == "identifier":
                        params.append(self.text(item))
        is_block = body is not None and body.type == "block"
        flow = self.add_node(
            "lambda",
            lam,
            host_scope,
            host.id,
            {"params": params, "body_kind": "block" if is_block else "expression"},
            code=self.header(lam, body).strip()
            + (" { … }" if is_block else f" {cst.short(self.text(body), 50)}"),
        )
        path = self.path_of(flow, self.base)
        if body is None:
            return
        saved = (self.jumps, self.handlers, self.exits)
        self.jumps, self.handlers, self.exits = [], [], []
        try:
            if is_block:
                first, _ = self.sequence(
                    cst.named_children(body), PathScope(prefix=f"{path}/"), flow.id
                )
                if first is not None:
                    self.edge(flow.id, first, "body")
            else:
                self.decorate(flow, [body])
        finally:
            self.jumps, self.handlers, self.exits = saved
