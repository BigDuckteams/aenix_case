"""Правила диагностики (S7.4–S7.5, docs/05 § 5): PERF-01/02/03/06, BUG-01/02, MAINT-01…05, 09.

Правила смотрят на CST метода с цепочкой объемлющих циклов и опираются на модель стоимости (какие
циклы действительно зависят от ``n``) и на выведенные типы. Узлы не сохраняются между вызовами.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from tree_sitter import Node

from engine.analysis import jdk_costs
from engine.analysis.complexity import Cost, N
from engine.analysis.cost_model import Contribution as CostContribution
from engine.analysis.cost_model import CostModel, CostResult, MethodCost
from engine.analysis.metrics import MethodMetrics, MetricsResult
from engine.analysis.model import (
    ComplexityEstimate,
    Contribution,
    Evidence,
    EvidenceItem,
    Finding,
    FindingLocation,
)
from engine.java import cst
from engine.java.project import FLOWABLE, JavaProject
from engine.java.semantic import Context
from engine.java.symbols import Member, base_name

DEFAULT_THRESHOLDS: dict[str, float] = {
    "max_method_lines": 30,
    "max_nesting": 3,
    "max_params": 5,
    "max_cyclomatic": 10,
    "max_class_lines": 400,
    "max_class_methods": 20,
}

_LOOPS = {"for_statement", "enhanced_for_statement", "while_statement", "do_statement"}
_EQUALITY_CALLS = re.compile(r"\.(?:equals|equalsIgnoreCase)\s*\(")
_COMPARE_ZERO = re.compile(r"\.compareTo\s*\([^)]*\)\s*==\s*0")
_LIST_TYPES = jdk_costs.LIST_LIKE | jdk_costs.LINKED


def reduced(cost: Cost) -> Cost:
    """Ожидаемая сложность после индексации/замены структуры: степень ``n`` снижается на 1."""
    if cost.exp or cost.n < 2:
        return cost
    return Cost(False, cost.n - 1, cost.log)


@dataclass(slots=True)
class LoopInfo:
    node_id: str
    kind: str
    variable: str | None
    source: str  # что перебирается: «orders», «i < n»
    factor: Cost
    start_line: int
    end_line: int


class AnalysisContext:
    """Данные, общие для правил: проект, стоимости, метрики и пороги."""

    def __init__(
        self,
        project: JavaProject,
        model: CostModel,
        metrics: MetricsResult,
        thresholds: dict[str, float],
    ) -> None:
        self.project = project
        self.model = model
        self.metrics = metrics
        self.thresholds = {**DEFAULT_THRESHOLDS, **thresholds}
        self.taken: dict[str, int] = {}

    def unique_id(self, rule_id: str, node_id: str) -> str:
        base = f"{rule_id}:{node_id}"
        self.taken[base] = self.taken.get(base, 0) + 1
        return base if self.taken[base] == 1 else f"{base}#{self.taken[base]}"


def estimate_of(result: CostResult, after: Cost | None = None) -> ComplexityEstimate:
    return ComplexityEstimate(
        current=result.cost.format(),
        after=after.format() if after is not None else None,
        confidence="heuristic" if result.notes else "exact",
        contributions=[Contribution(c.node_id, c.factor, c.why) for c in result.chain],
        reason="; ".join(sorted(result.notes)) or None,
    )


# --- обход метода с объемлющими циклами ----------------------------------------------------------------


class MemberView:
    """Метод проекта: CST, контекст разрешения типов и объемлющие циклы узла."""

    def __init__(self, project: JavaProject, model: CostModel | None, member: Member) -> None:
        self.member = member
        self.file = project.file_of(member)
        self.context: Context
        self.context, declaration = project.context(member)
        self.parsed = self.context.parsed
        self.declaration = declaration
        self.cost: MethodCost | None = model.method(member.id) if model is not None else None

    def text(self, node: Node | None) -> str:
        return cst.text_of(self.parsed, node)

    def fid(self, node: Node) -> str:
        if self.cost is None:
            return self.member.id
        span = self.parsed.range_of(node)
        return self.cost.flow_ids.get((span.start.line, span.start.column), self.member.id)

    def lines(self, node: Node) -> tuple[int, int]:
        span = self.parsed.range_of(node)
        return span.start.line, span.end.line

    def report_lines(self, node: Node) -> tuple[int, int]:
        """Строки для находки: у ``if`` — только условие, а не вся ветвь."""
        if node.type == "if_statement":
            condition = node.child_by_field_name("condition")
            if condition is not None:
                return self.lines(condition)
        return self.lines(node)

    def body(self) -> Node | None:
        if self.declaration is None:
            return None
        return self.declaration.child_by_field_name("body") or cst.first_child_of_type(
            self.declaration, "block"
        )

    def variable_of(self, loop: Node) -> str | None:
        if loop.type == "enhanced_for_statement":
            return self.text(loop.child_by_field_name("name")) or None
        if loop.type == "for_statement":
            for item in loop.children_by_field_name("init"):
                declarators = cst.children_of_type(item, "variable_declarator")
                if declarators:
                    return self.text(declarators[0].child_by_field_name("name")) or None
        return None

    def source_of(self, loop: Node) -> str:
        if loop.type == "enhanced_for_statement":
            return self.text(loop.child_by_field_name("value"))
        return self.text(loop.child_by_field_name("condition")).strip("()")

    def loop_info(self, loop: Node) -> LoopInfo:
        node_id = self.fid(loop)
        factor = self.cost.loops.get(node_id, N) if self.cost is not None else N
        start, end = self.lines(loop)
        return LoopInfo(
            node_id, loop.type, self.variable_of(loop), self.source_of(loop), factor, start, end
        )

    def enclosing_loops(self, node: Node) -> list[LoopInfo]:
        """Циклы, чьё тело (или условие/шаг) выполняется на каждой итерации; внешние — первыми."""
        found: list[LoopInfo] = []
        child = node
        parent = node.parent
        while parent is not None and (self.declaration is None or parent.id != self.declaration.id):
            if parent.type in _LOOPS and not self._evaluated_once(parent, child):
                found.append(self.loop_info(parent))
            if parent.type == "lambda_expression":
                break
            child, parent = parent, parent.parent
        found.reverse()
        return found

    @staticmethod
    def _evaluated_once(loop: Node, child: Node) -> bool:
        """Часть цикла, вычисляемая один раз: итерируемое выражение for-each и ``init`` обычного for."""
        if loop.type == "enhanced_for_statement":
            value = loop.child_by_field_name("value")
            return value is not None and value.id == child.id
        if loop.type == "for_statement":
            return any(item.id == child.id for item in loop.children_by_field_name("init"))
        return False

    def references_of(self, name: str, scope: Node) -> list[Node]:
        """Чтения и записи переменной ``name`` в поддереве, кроме её собственного объявления."""
        found = []
        for node in cst.walk(scope):
            if node.type != "identifier" or self.text(node) != name or node.parent is None:
                continue
            parent = node.parent
            if parent.type == "variable_declarator" and parent.child_by_field_name("name") == node:
                continue
            if parent.type == "method_invocation" and parent.child_by_field_name("name") == node:
                continue
            if parent.type == "field_access" and parent.child_by_field_name("field") == node:
                continue
            found.append(node)
        return found

    def statement_of(self, node: Node) -> Node:
        """Ближайший объемлющий оператор (для строк и узла блок-схемы)."""
        current = node
        while current.parent is not None and current.type not in (
            "expression_statement",
            "local_variable_declaration",
            "return_statement",
            "if_statement",
            "throw_statement",
        ):
            if self.declaration is not None and current.parent.id == self.declaration.id:
                break
            current = current.parent
        return current

    def declared_inside(self, name: str, scope: Node) -> bool:
        for item in cst.walk(scope):
            if (
                item.type == "variable_declarator"
                and self.text(item.child_by_field_name("name")) == name
            ):
                return True
        return False

    def type_of_name(self, name: str) -> str | None:
        declared = self.context.scope.get(name)
        if declared:
            return base_name(declared) or None
        found = self.project_field_type(name)
        return found

    def project_field_type(self, name: str) -> str | None:
        found = self.context.table.field_type(self.context.owner, name)
        return base_name(found[0].type_text or "") if found else None


def _location(view: MemberView, node: Node, node_id: str | None = None) -> FindingLocation:
    start, end = view.report_lines(node)
    return FindingLocation(view.file, start, end, node_id or view.fid(node), view.member.id)


def _members(ctx: AnalysisContext) -> list[Member]:
    return [m for m in ctx.project.members() if m.kind in FLOWABLE]


def _node_cost(view: MemberView, node_id: str) -> CostResult | None:
    return view.cost.node_costs.get(node_id) if view.cost is not None else None


# --- PERF-01: вложенный цикл поиска/слияния -------------------------------------------------------------


def _identifiers(view: MemberView, node: Node | None) -> set[str]:
    if node is None:
        return set()
    return {view.text(n) for n in cst.walk(node) if n.type == "identifier"}


def _key_comparison(view: MemberView, condition: Node, outer: str, inner: str) -> bool:
    text = view.text(condition)
    if _EQUALITY_CALLS.search(text) or _COMPARE_ZERO.search(text):
        return True
    for node in cst.walk(condition):
        if (
            node.type != "binary_expression"
            or view.text(node.child_by_field_name("operator")) != "=="
        ):
            continue
        left = _identifiers(view, node.child_by_field_name("left"))
        right = _identifiers(view, node.child_by_field_name("right"))
        if (outer in left and inner in right and outer not in right and inner not in left) or (
            inner in left and outer in right and inner not in right and outer not in left
        ):
            return True
    return False


def rule_perf_01(ctx: AnalysisContext) -> list[Finding]:
    found: list[Finding] = []
    seen: set[str] = set()
    for member in _members(ctx):
        view = MemberView(ctx.project, ctx.model, member)
        body = view.body()
        if body is None:
            continue
        for node in cst.walk(body):
            if node.type != "if_statement":
                continue
            condition = node.child_by_field_name("condition")
            loops = [
                lp for lp in view.enclosing_loops(node) if lp.variable and not lp.factor.is_constant
            ]
            names = _identifiers(view, condition)
            pair = next(
                (
                    (outer, inner)
                    for i, outer in enumerate(loops)
                    for inner in loops[i + 1 :]
                    if outer.variable in names
                    and inner.variable in names
                    and condition is not None
                    and _key_comparison(view, condition, outer.variable or "", inner.variable or "")
                ),
                None,
            )
            if pair is None or pair[0].node_id in seen:
                continue
            outer, inner = pair
            seen.add(outer.node_id)
            result = _node_cost(view, outer.node_id) or CostResult()
            after = reduced(result.cost)
            same = outer.source == inner.source
            where = (
                f"Внешний и внутренний циклы обходят {outer.source}"
                if same
                else f"Внешний цикл обходит {outer.source}, внутренний — {inner.source}"
            )
            found.append(
                Finding(
                    id=ctx.unique_id("PERF-01", outer.node_id),
                    rule_id="PERF-01",
                    severity="high",
                    category="PERF",
                    title=f"Вложенный цикл — {result.cost.format()}",
                    location=FindingLocation(
                        view.file, outer.start_line, outer.end_line, outer.node_id, member.id
                    ),
                    explanation=(
                        f"{where}; условие `{view.text(condition)}` сравнивает ключи двух элементов, "
                        "поэтому каждая пара проверяется отдельно, а число сравнений растёт как n²."
                    ),
                    defect="Квадратичный поиск совпадений: каждый элемент сравнивается со всеми остальными.",
                    risk="Время растёт квадратично с размером входа: на больших данных программа «зависает».",
                    recommendation=(
                        f"Индексировать элементы по ключу (`Map`) за один проход: поиск пары станет O(1), "
                        f"итог — {after.format()}."
                    ),
                    evidence=Evidence(
                        static=[
                            EvidenceItem("loop", f"внешний цикл по {outer.source}", outer.node_id),
                            EvidenceItem(
                                "loop", f"внутренний цикл по {inner.source}", inner.node_id
                            ),
                            EvidenceItem("condition", view.text(condition)),
                        ]
                    ),
                    complexity=estimate_of(result, after),
                )
            )
    return found


# --- PERF-02 / PERF-06: операции над коллекциями в цикле ----------------------------------------------


def _call_parts(view: MemberView, call: Node) -> tuple[str, Node | None, list[Node], str | None]:
    name = view.text(call.child_by_field_name("name"))
    receiver = call.child_by_field_name("object")
    arguments = call.child_by_field_name("arguments")
    args = cst.named_children(arguments) if arguments is not None else []
    receiver_type = view.context.expr_type(receiver) if receiver is not None else None
    return name, receiver, args, receiver_type


def _loop_scope_declares(view: MemberView, loops: list[LoopInfo], name: str, node: Node) -> bool:
    """Коллекция объявлена внутри самого цикла: размер не растёт с ``n`` (эвристика)."""
    parent = node.parent
    while parent is not None:
        if parent.type in _LOOPS:
            body = parent.child_by_field_name("body")
            if body is not None and view.declared_inside(name, body):
                return True
        parent = parent.parent
    return False


def _loop_finding(
    ctx: AnalysisContext,
    view: MemberView,
    rule_id: str,
    severity: str,
    title: str,
    call: Node,
    loops: list[LoopInfo],
    texts: tuple[str, str, str, str],
    evidence: list[EvidenceItem],
    per_iteration: tuple[Cost, str] | None = None,
) -> Finding:
    """Находка PERF в цикле. ``per_iteration`` — стоимость операции за итерацию, которой нет в каталоге
    (копирование строки, сдвиг массива): она умножает стоимость цикла, а «после» — стоимость цикла."""
    outer = next(lp for lp in loops if not lp.factor.is_constant)
    result = _node_cost(view, outer.node_id) or CostResult()
    statement = view.statement_of(call)
    if per_iteration is None:
        after = reduced(result.cost)
    else:
        factor, why = per_iteration
        after = result.cost
        # работа за итерацию складывается с телом цикла (максимум), а не умножает его целиком
        combined = outer.factor * factor
        if combined > result.cost:
            result = CostResult(
                combined,
                (*result.chain[:1], CostContribution(view.fid(call), factor.factor(), why)),
                result.notes,
            )
    explanation, defect, risk, recommendation = texts
    return Finding(
        id=ctx.unique_id(rule_id, view.fid(statement)),
        rule_id=rule_id,
        severity=severity,
        category="PERF",
        title=title,
        location=_location(view, statement),
        explanation=explanation,
        defect=defect,
        risk=risk,
        recommendation=recommendation.format(after=after.format()),
        evidence=Evidence(static=evidence),
        complexity=estimate_of(result, after),
    )


def rule_perf_02(ctx: AnalysisContext) -> list[Finding]:
    found: list[Finding] = []
    for member in _members(ctx):
        view = MemberView(ctx.project, ctx.model, member)
        body = view.body()
        if body is None:
            continue
        for call in (n for n in cst.walk(body) if n.type == "method_invocation"):
            name, receiver, args, receiver_type = _call_parts(view, call)
            if receiver is None or receiver_type not in _LIST_TYPES or len(args) != 1:
                continue
            if name == "remove" and view.context.expr_type(args[0]) == "int":
                continue
            if name not in {"contains", "indexOf", "lastIndexOf", "remove"}:
                continue
            loops = view.enclosing_loops(call)
            if not any(not lp.factor.is_constant for lp in loops):
                continue
            receiver_text = view.text(receiver)
            if receiver.type == "identifier" and _loop_scope_declares(
                view, loops, receiver_text, call
            ):
                continue
            loop = next(lp for lp in loops if not lp.factor.is_constant)
            found.append(
                _loop_finding(
                    ctx,
                    view,
                    "PERF-02",
                    "high",
                    f"Линейный поиск `{name}` в цикле",
                    call,
                    loops,
                    (
                        f"`{receiver_text}.{name}(…)` по списку просматривает элементы по порядку, а вызов "
                        f"повторяется на каждой итерации цикла по {loop.source}: итого O(n) × O(n).",
                        f"Линейный поиск по `{receiver_type}` внутри цикла.",
                        "Время растёт квадратично: список из 100 000 элементов даёт ~10¹⁰ сравнений.",
                        "Заменить список на `HashSet`/`HashMap` для проверок наличия: итог — {after}.",
                    ),
                    [
                        EvidenceItem("call", f"{receiver_text}.{name}(…)", view.fid(call)),
                        EvidenceItem("loop", f"цикл по {loop.source}", loop.node_id),
                        EvidenceItem("collection", f"{receiver_text}: {receiver_type}"),
                    ],
                )
            )
    return found


def rule_perf_06(ctx: AnalysisContext) -> list[Finding]:
    found: list[Finding] = []
    for member in _members(ctx):
        view = MemberView(ctx.project, ctx.model, member)
        body = view.body()
        if body is None:
            continue
        for call in (n for n in cst.walk(body) if n.type == "method_invocation"):
            name, receiver, args, receiver_type = _call_parts(view, call)
            if receiver is None:
                continue
            indexed_linked = receiver_type == "LinkedList" and name in {"get", "set"} and args
            front_insert = (
                receiver_type in {"ArrayList", "Vector"}
                and name == "add"
                and len(args) == 2
                and view.text(args[0]) == "0"
            )
            if not (indexed_linked or front_insert):
                continue
            loops = view.enclosing_loops(call)
            if not any(not lp.factor.is_constant for lp in loops):
                continue
            receiver_text = view.text(receiver)
            if receiver.type == "identifier" and _loop_scope_declares(
                view, loops, receiver_text, call
            ):
                continue
            loop = next(lp for lp in loops if not lp.factor.is_constant)
            if indexed_linked:
                texts = (
                    f"`{receiver_text}.{name}(i)` у `LinkedList` проходит по цепочке узлов — O(n), и вызывается "
                    f"на каждой итерации цикла по {loop.source}.",
                    "Доступ по индексу к связному списку.",
                    "Время растёт квадратично с длиной списка.",
                    "Использовать `ArrayList` (доступ по индексу O(1)) или итератор: итог — {after}.",
                )
            else:
                texts = (
                    f"`{receiver_text}.add(0, …)` сдвигает все элементы `ArrayList`, и вставка в начало "
                    f"повторяется на каждой итерации цикла по {loop.source}.",
                    "Вставка в начало массивного списка в цикле.",
                    "Время растёт квадратично с числом вставок.",
                    "Использовать `ArrayDeque.addFirst` или собирать в конец и развернуть: итог — {after}.",
                )
            found.append(
                _loop_finding(
                    ctx,
                    view,
                    "PERF-06",
                    "medium",
                    "Неподходящая коллекция в цикле",
                    call,
                    loops,
                    texts,
                    [
                        EvidenceItem("call", f"{receiver_text}.{name}(…)", view.fid(call)),
                        EvidenceItem("collection", f"{receiver_text}: {receiver_type}"),
                        EvidenceItem("loop", f"цикл по {loop.source}", loop.node_id),
                    ],
                    (N, "вставка в начало сдвигает все элементы") if front_insert else None,
                )
            )
    return found


# --- PERF-03: конкатенация строк в цикле -------------------------------------------------------------------


def rule_perf_03(ctx: AnalysisContext) -> list[Finding]:
    found: list[Finding] = []
    for member in _members(ctx):
        view = MemberView(ctx.project, ctx.model, member)
        body = view.body()
        if body is None:
            continue
        for node in (n for n in cst.walk(body) if n.type == "assignment_expression"):
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            operator = view.text(node.child_by_field_name("operator"))
            if left is None or right is None or left.type != "identifier":
                continue
            name = view.text(left)
            if view.type_of_name(name) != "String":
                continue
            concatenates = operator == "+=" or (
                operator == "="
                and right.type == "binary_expression"
                and view.text(right.child_by_field_name("operator")) == "+"
                and name in _identifiers(view, right.child_by_field_name("left"))
            )
            if not concatenates:
                continue
            loops = view.enclosing_loops(node)
            if not any(not lp.factor.is_constant for lp in loops):
                continue
            if _loop_scope_declares(view, loops, name, node):
                continue
            loop = next(lp for lp in loops if not lp.factor.is_constant)
            found.append(
                _loop_finding(
                    ctx,
                    view,
                    "PERF-03",
                    "medium",
                    "Конкатенация строк в цикле",
                    node,
                    loops,
                    (
                        f"`{name}` — неизменяемая `String`: каждая конкатенация копирует накопленный текст, "
                        f"а выполняется она на каждой итерации цикла по {loop.source}.",
                        "Квадратичное копирование при построении строки.",
                        "Время и память растут квадратично с длиной результата.",
                        "Накапливать в `StringBuilder` и вызвать `toString()` после цикла: итог — {after}.",
                    ),
                    [
                        EvidenceItem("assignment", view.text(node), view.fid(node)),
                        EvidenceItem("loop", f"цикл по {loop.source}", loop.node_id),
                    ],
                    (N, f"конкатенация копирует накопленную строку `{name}`"),
                )
            )
    return found


# --- BUG-01 / BUG-02 --------------------------------------------------------------------------------------------


_ELEMENT_GETTERS = frozenset(
    {"get", "getFirst", "getLast", "remove", "poll", "peek", "pop", "next", "element"}
)
_VALUE_GETTERS = frozenset({"get", "getOrDefault", "remove", "put"})


def _generic_arguments(type_text: str) -> list[str]:
    """Аргументы верхнего уровня: ``Map<String, List<Integer>>`` → ``['String', 'List<Integer>']``."""
    start = type_text.find("<")
    if start < 0 or not type_text.rstrip().endswith(">"):
        return []
    depth, current, parts = 0, "", []
    for char in type_text[start + 1 : type_text.rstrip().rfind(">")]:
        if char == "<":
            depth += 1
        elif char == ">":
            depth -= 1
        if char == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += char
    parts.append(current.strip())
    return parts


def is_string(view: MemberView, node: Node) -> bool:
    """Выражение типа ``String``, в том числе элемент ``List<String>`` и значение ``Map<K, String>``."""
    if view.context.expr_type(node) == "String":
        return True
    if node.type != "method_invocation":
        return False
    receiver = node.child_by_field_name("object")
    if receiver is None or receiver.type != "identifier":
        return False
    name = view.text(receiver)
    declared = view.context.scope.get(name)
    if declared is None:
        field = view.context.table.field_type(view.context.owner, name)
        declared = field[0].type_text if field else None
    if not declared:
        return False
    owner = base_name(declared)
    arguments = _generic_arguments(declared)
    method = view.text(node.child_by_field_name("name"))
    if (
        method in _ELEMENT_GETTERS
        and arguments
        and jdk_costs.is_collection(owner)
        and owner
        not in (
            jdk_costs.HASHED & {"Map", "HashMap", "LinkedHashMap", "TreeMap", "ConcurrentHashMap"}
        )
    ):
        return base_name(arguments[0]) == "String"
    if (
        method in _VALUE_GETTERS
        and len(arguments) == 2
        and owner in jdk_costs.HASHED | jdk_costs.TREED
    ):
        return base_name(arguments[1]) == "String"
    return False


def rule_bug_01(ctx: AnalysisContext) -> list[Finding]:
    found: list[Finding] = []
    for member in _members(ctx):
        view = MemberView(ctx.project, ctx.model, member)
        body = view.body()
        if body is None:
            continue
        for node in (n for n in cst.walk(body) if n.type == "binary_expression"):
            operator = view.text(node.child_by_field_name("operator"))
            if operator not in {"==", "!="}:
                continue
            left, right = node.child_by_field_name("left"), node.child_by_field_name("right")
            if left is None or right is None or "null_literal" in (left.type, right.type):
                continue
            if not (is_string(view, left) or is_string(view, right)):
                continue
            statement = view.statement_of(node)
            equals = f"`{view.text(left)}.equals({view.text(right)})`"
            found.append(
                Finding(
                    id=ctx.unique_id("BUG-01", view.fid(statement)),
                    rule_id="BUG-01",
                    severity="high",
                    category="BUG",
                    title="Сравнение строк через `==`",
                    location=_location(view, statement),
                    explanation=(
                        f"`{view.text(node)}` сравнивает ссылки, а не содержимое строк: результат зависит от "
                        "того, указывают ли обе переменные на один и тот же объект."
                    ),
                    defect="Сравнение ссылок вместо значений строк.",
                    risk="Результат верен только для литералов из пула строк; для введённых или собранных строк — нет.",
                    recommendation=f"Сравнивать содержимое: {equals} (или `Objects.equals`).",
                    evidence=Evidence(
                        static=[EvidenceItem("expression", view.text(node), view.fid(statement))]
                    ),
                )
            )
    return found


def rule_bug_02(ctx: AnalysisContext) -> list[Finding]:
    found: list[Finding] = []
    for member in _members(ctx):
        view = MemberView(ctx.project, ctx.model, member)
        body = view.body()
        if body is None:
            continue
        for node in (n for n in cst.walk(body) if n.type == "catch_clause"):
            handler = node.child_by_field_name("body")
            if handler is None or cst.named_children(handler):
                continue
            catch_type = view.text(cst.first_child_of_type(node, "catch_formal_parameter")).split(
                " "
            )[0]
            found.append(
                Finding(
                    id=ctx.unique_id("BUG-02", view.fid(node)),
                    rule_id="BUG-02",
                    severity="medium",
                    category="BUG",
                    title="Пустой блок `catch`",
                    location=_location(view, node),
                    explanation=f"Блок `catch ({catch_type} …)` не содержит операторов: исключение гасится молча.",
                    defect="Проглоченное исключение.",
                    risk="Ошибки остаются незамеченными, а программа продолжает работать в неверном состоянии.",
                    recommendation="Обработать исключение, залогировать его или пробросить дальше.",
                    evidence=Evidence(
                        static=[EvidenceItem("catch", f"catch ({catch_type})", view.fid(node))]
                    ),
                )
            )
    return found


# --- MAINT: по метрикам ------------------------------------------------------------------------------------------


def _method_location(ctx: AnalysisContext, method_id: str) -> FindingLocation:
    member = ctx.project.member(method_id)
    assert member is not None
    path = ctx.project.file_of(member)
    span = ctx.project.parsed(path).lines.range(member.start_byte, member.end_byte)
    return FindingLocation(path, span.start.line, span.end.line, method_id, method_id)


def _by_method(
    ctx: AnalysisContext,
    rule_id: str,
    category: str,
    pick: Callable[[MethodMetrics], bool],
    build: Callable[[MethodMetrics], tuple[str, str, str, str, str, str]],
    severity: Callable[[MethodMetrics], str],
) -> list[Finding]:
    findings: list[Finding] = []
    for metric in ctx.metrics.metrics.methods:
        if not pick(metric):
            continue
        title, explanation, defect, risk, recommendation, kind = build(metric)
        method_id = metric.method_id
        cost = ctx.model.method(method_id)
        findings.append(
            Finding(
                id=ctx.unique_id(rule_id, method_id),
                rule_id=rule_id,
                severity=severity(metric),
                category=category,
                title=title,
                location=_method_location(ctx, method_id),
                explanation=explanation,
                defect=defect,
                risk=risk,
                recommendation=recommendation,
                evidence=Evidence(
                    static=[EvidenceItem(kind, explanation.split(".")[0], method_id)]
                ),
                complexity=estimate_of(cost.result) if cost is not None else None,
            )
        )
    return findings


def rule_maint_01(ctx: AnalysisContext) -> list[Finding]:
    limit = ctx.thresholds["max_method_lines"]
    return _by_method(
        ctx,
        "MAINT-01",
        "MAINT",
        lambda m: m.lines > limit,
        lambda m: (
            f"Длинный метод: {m.name}() — {m.lines} строк",
            f"Метод {m.name}() занимает {m.lines} строк кода при пороге {int(limit)}.",
            "Метод делает слишком много и плохо читается.",
            "Трудно понять, проверить и изменить без побочных эффектов.",
            "Выделить из метода логически завершённые части в отдельные методы.",
            "method",
        ),
        lambda m: "medium" if m.lines > 2 * limit else "low",
    )


def rule_maint_03(ctx: AnalysisContext) -> list[Finding]:
    limit = ctx.thresholds["max_nesting"]
    return _by_method(
        ctx,
        "MAINT-03",
        "MAINT",
        lambda m: m.max_nesting > limit,
        lambda m: (
            f"Глубокая вложенность в {m.name}() — {m.max_nesting}",
            f"Вложенность операторов в {m.name}() достигает {m.max_nesting} при пороге {int(limit)}.",
            "Много уровней вложенных условий и циклов.",
            "Код тяжело читать, легко ошибиться при изменении.",
            "Использовать ранние возвраты или выделить вложенную часть в метод.",
            "nesting",
        ),
        lambda m: "low",
    )


def rule_maint_04(ctx: AnalysisContext) -> list[Finding]:
    limit = ctx.thresholds["max_params"]
    return _by_method(
        ctx,
        "MAINT-04",
        "MAINT",
        lambda m: m.params > limit,
        lambda m: (
            f"Много параметров у {m.name}() — {m.params}",
            f"Метод {m.name}() принимает {m.params} параметров при пороге {int(limit)}.",
            "Длинный список параметров.",
            "Легко перепутать порядок аргументов, сложно расширять.",
            "Сгруппировать параметры в `record` или объект параметров.",
            "params",
        ),
        lambda m: "low",
    )


def rule_maint_09(ctx: AnalysisContext) -> list[Finding]:
    limit = ctx.thresholds["max_cyclomatic"]
    return _by_method(
        ctx,
        "MAINT-09",
        "MAINT",
        lambda m: m.cyclomatic > limit,
        lambda m: (
            f"Сложный метод {m.name}() — цикломатика {m.cyclomatic}",
            f"Цикломатическая сложность {m.name}() равна {m.cyclomatic} при пороге {int(limit)}.",
            "Слишком много ветвлений в одном методе.",
            "Число путей выполнения велико: сложно покрыть тестами.",
            "Разбить метод на части по ветвям логики.",
            "cyclomatic",
        ),
        lambda m: "medium" if m.cyclomatic > 2 * limit else "low",
    )


def rule_maint_02(ctx: AnalysisContext) -> list[Finding]:
    found: list[Finding] = []
    for clone in ctx.metrics.clones:
        first, second = clone.first, clone.second
        node_id = f"{first.method_id}/stmt[{first.first}]"
        found.append(
            Finding(
                id=ctx.unique_id("MAINT-02", node_id),
                rule_id="MAINT-02",
                severity="medium",
                category="MAINT",
                title=f"Дублирование логики: {clone.statements} операторов",
                location=FindingLocation(
                    first.file, first.start_line, first.end_line, None, first.method_id
                ),
                explanation=(
                    f"Строки {first.file}:{first.start_line}-{first.end_line} повторяются в "
                    f"{second.file}:{second.start_line}-{second.end_line} с точностью до имён и литералов."
                ),
                defect="Клон кода: одна и та же логика записана дважды.",
                risk="Исправление в одном месте легко забыть во втором.",
                recommendation="Выделить общий метод и заменить оба фрагмента его вызовом.",
                evidence=Evidence(
                    static=[
                        EvidenceItem(
                            "clone",
                            f"{first.file}:{first.start_line}-{first.end_line}",
                            first.method_id,
                        ),
                        EvidenceItem(
                            "clone",
                            f"{second.file}:{second.start_line}-{second.end_line}",
                            second.method_id,
                        ),
                    ]
                ),
            )
        )
    return found


def rule_maint_05(ctx: AnalysisContext) -> list[Finding]:
    found: list[Finding] = []
    max_lines, max_methods = ctx.thresholds["max_class_lines"], ctx.thresholds["max_class_methods"]
    for metric in ctx.metrics.metrics.types:
        big = metric.lines > max_lines or metric.methods > max_methods
        scattered = metric.lcom4 >= 2 and metric.methods >= 8
        if not (big or scattered):
            continue
        reasons = []
        if metric.lines > max_lines:
            reasons.append(f"{metric.lines} строк (порог {int(max_lines)})")
        if metric.methods > max_methods:
            reasons.append(f"{metric.methods} методов (порог {int(max_methods)})")
        if scattered:
            reasons.append(f"несвязные группы методов (LCOM4 = {metric.lcom4:g})")
        path = metric.file
        decl = next(d for d in ctx.project.types() if d.id == metric.type_id)
        span = ctx.project.parsed(path).lines.range(decl.start_byte, decl.end_byte)
        found.append(
            Finding(
                id=ctx.unique_id("MAINT-05", metric.type_id),
                rule_id="MAINT-05",
                severity="high"
                if metric.lines > max_lines and metric.methods > max_methods
                else "medium",
                category="MAINT",
                title=f"Монолитный класс {metric.name}",
                location=FindingLocation(
                    path, span.start.line, span.end.line, metric.type_id, None
                ),
                explanation=f"Класс {metric.name}: " + "; ".join(reasons) + ".",
                defect="Класс совмещает несколько ответственностей.",
                risk="Любое изменение затрагивает весь класс, сложно тестировать части отдельно.",
                recommendation="Разделить класс на несколько по группам связанных методов и полей.",
                evidence=Evidence(
                    static=[EvidenceItem("class", "; ".join(reasons), metric.type_id)]
                ),
            )
        )
    return found


RULES: tuple[Callable[[AnalysisContext], list[Finding]], ...] = (
    rule_perf_01,
    rule_perf_02,
    rule_perf_03,
    rule_perf_06,
    rule_bug_01,
    rule_bug_02,
    rule_maint_01,
    rule_maint_02,
    rule_maint_03,
    rule_maint_04,
    rule_maint_05,
    rule_maint_09,
)
