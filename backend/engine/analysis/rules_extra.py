"""Расширение каталога правил (S7.6): PERF-04, PERF-08, BUG-07, BUG-09, BUG-10, MAINT-06, 07, 10."""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from tree_sitter import Node

from engine.analysis import jdk_costs
from engine.analysis.complexity import N
from engine.analysis.cost_model import CostResult
from engine.analysis.model import (
    Evidence,
    EvidenceItem,
    Finding,
    FindingLocation,
)
from engine.analysis.rules import (
    AnalysisContext,
    MemberView,
    _loop_finding,
    _members,
    estimate_of,
    is_string,
)
from engine.java import cst
from engine.java.project import FLOWABLE
from engine.java.symbols import Member, base_name

_NUMBER = {
    "decimal_integer_literal",
    "hex_integer_literal",
    "octal_integer_literal",
    "binary_integer_literal",
    "decimal_floating_point_literal",
}
_ALLOWED_NUMBERS = {"0", "1", "0L", "1L", "0.0", "1.0", "0.0f", "1.0f", "0d", "1d"}
_DISCARDED = frozenset(
    {
        "trim",
        "strip",
        "replace",
        "replaceAll",
        "replaceFirst",
        "toLowerCase",
        "toUpperCase",
        "substring",
        "concat",
        "repeat",
        "stripLeading",
        "stripTrailing",
    }
)
_MUTATORS = frozenset(
    {"remove", "add", "clear", "addAll", "removeAll", "removeIf", "retainAll", "put"}
)
_SORT_CALLS = {("Collections", "sort"), ("Arrays", "sort")}
_CAMEL_METHOD = re.compile(r"^[a-z][A-Za-z0-9]*$")
_PASCAL_TYPE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_CONSTANT = re.compile(r"^[A-Z][A-Z0-9_]*$")


# --- PERF-04: сортировка внутри цикла --------------------------------------------------------------------------


def rule_perf_04(ctx: AnalysisContext) -> list[Finding]:
    found: list[Finding] = []
    for member in _members(ctx):
        view = MemberView(ctx.project, ctx.model, member)
        body = view.body()
        if body is None:
            continue
        for call in (n for n in cst.walk(body) if n.type == "method_invocation"):
            name = view.text(call.child_by_field_name("name"))
            receiver = call.child_by_field_name("object")
            if name != "sort" or receiver is None:
                continue
            owner = view.text(receiver)
            args = call.child_by_field_name("arguments")
            argument = (
                cst.named_children(args)[0]
                if args is not None and cst.named_children(args)
                else None
            )
            is_static = (owner, "sort") in _SORT_CALLS
            target = view.text(argument) if is_static and argument is not None else owner
            if (
                not is_static
                and view.context.expr_type(receiver) not in jdk_costs.LIST_LIKE | jdk_costs.LINKED
            ):
                continue
            loops = view.enclosing_loops(call)
            if not any(not lp.factor.is_constant for lp in loops):
                continue
            if target.isidentifier() and any(
                _declared_in(view, loop_node, target) for loop_node in _loop_nodes(call)
            ):
                continue
            loop = next(lp for lp in loops if not lp.factor.is_constant)
            found.append(
                _loop_finding(
                    ctx,
                    view,
                    "PERF-04",
                    "medium",
                    "Сортировка внутри цикла",
                    call,
                    loops,
                    (
                        f"`{view.text(call)}` сортирует `{target}` на каждой итерации цикла по {loop.source}: "
                        "стоимость сортировки умножается на число итераций.",
                        "Повторная сортировка одних и тех же данных.",
                        "Время растёт как n² log n.",
                        "Отсортировать один раз до цикла, если коллекция в цикле не меняется: итог — {after}.",
                    ),
                    [
                        EvidenceItem("call", view.text(call), view.fid(call)),
                        EvidenceItem("loop", f"цикл по {loop.source}", loop.node_id),
                    ],
                )
            )
    return found


def _loop_nodes(node: Node) -> list[Node]:
    result = []
    parent = node.parent
    while parent is not None:
        if parent.type in {
            "for_statement",
            "enhanced_for_statement",
            "while_statement",
            "do_statement",
        }:
            result.append(parent)
        parent = parent.parent
    return result


def _declared_in(view: MemberView, loop: Node, name: str) -> bool:
    body = loop.child_by_field_name("body")
    return body is not None and view.declared_inside(name, body)


# --- PERF-08: рекурсия без мемоизации -----------------------------------------------------------------------------


def rule_perf_08(ctx: AnalysisContext) -> list[Finding]:
    found: list[Finding] = []
    for member in _members(ctx):
        computed = ctx.model.method(member.id)
        if computed is None or not computed.cost.exp or not computed.recursion:
            continue
        view = MemberView(ctx.project, ctx.model, member)
        body = view.body()
        if body is None:
            continue
        uses_cache = any(
            n.type in {"type_identifier", "identifier"}
            and view.text(n) in {"Map", "HashMap", "memo", "cache", "cached"}
            for n in cst.walk(view.declaration or body)
        )
        field_cache = any(
            m.kind == "field" and base_name(m.type_text or "") in jdk_costs.HASHED
            for t in ctx.project.types()
            for m in t.members
            if member in t.members
        )
        if uses_cache or field_cache:
            continue
        declaration = view.declaration
        assert declaration is not None
        start, end = view.lines(declaration)
        result = CostResult(computed.cost, computed.result.chain, computed.result.notes)
        found.append(
            Finding(
                id=ctx.unique_id("PERF-08", member.id),
                rule_id="PERF-08",
                severity="medium",
                category="PERF",
                title=f"Рекурсия без мемоизации: {member.name}()",
                location=FindingLocation(view.file, start, end, member.id, member.id),
                explanation=(
                    f"{member.name}() вызывает себя несколько раз с уменьшающимся аргументом: одни и те же "
                    "подзадачи пересчитываются, число вызовов растёт экспоненциально."
                ),
                defect="Повторное вычисление одинаковых подзадач.",
                risk="Время растёт как 2ⁿ: уже при n ≈ 40 программа практически не завершается.",
                recommendation="Запоминать результаты в `Map` (мемоизация) или перейти к итеративному решению: итог — O(n).",
                evidence=Evidence(
                    static=[EvidenceItem("recursion", computed.recursion or "", member.id)]
                ),
                complexity=estimate_of(result, N),
            )
        )
    return found


# --- BUG-07: результат метода String отброшен ---------------------------------------------------------------------


def rule_bug_07(ctx: AnalysisContext) -> list[Finding]:
    found: list[Finding] = []
    for member in _members(ctx):
        view = MemberView(ctx.project, ctx.model, member)
        body = view.body()
        if body is None:
            continue
        for node in (n for n in cst.walk(body) if n.type == "expression_statement"):
            call = cst.first_child_of_type(node, "method_invocation")
            if call is None or call.parent is None or call.parent.id != node.id:
                continue
            name = view.text(call.child_by_field_name("name"))
            receiver = call.child_by_field_name("object")
            if name not in _DISCARDED or receiver is None or not is_string(view, receiver):
                continue
            start, end = view.lines(node)
            found.append(
                Finding(
                    id=ctx.unique_id("BUG-07", view.fid(node)),
                    rule_id="BUG-07",
                    severity="high",
                    category="BUG",
                    title=f"Результат `{name}` не используется",
                    location=FindingLocation(view.file, start, end, view.fid(node), member.id),
                    explanation=(
                        f"`{view.text(call)}` возвращает новую строку: `String` неизменяема, "
                        "а результат отброшен, поэтому вызов ничего не меняет."
                    ),
                    defect="Вызов без эффекта: результат метода String не присваивается.",
                    risk="Строка остаётся прежней: нормализация, обрезка или замена не происходят.",
                    recommendation=f"Присвоить результат: `{view.text(receiver)} = {view.text(call)};`.",
                    evidence=Evidence(
                        static=[EvidenceItem("call", view.text(call), view.fid(node))]
                    ),
                )
            )
    return found


# --- BUG-09: изменение коллекции во время обхода ------------------------------------------------------------------


def _leaves_loop_after(statement: Node) -> bool:
    """После изменения следует ``break``/``return`` — итератор уже не используется."""
    sibling = statement.next_named_sibling
    while sibling is not None and sibling.type in {"line_comment", "block_comment"}:
        sibling = sibling.next_named_sibling
    return sibling is not None and sibling.type in {"break_statement", "return_statement"}


def rule_bug_09(ctx: AnalysisContext) -> list[Finding]:
    found: list[Finding] = []
    for member in _members(ctx):
        view = MemberView(ctx.project, ctx.model, member)
        body = view.body()
        if body is None:
            continue
        for loop in (n for n in cst.walk(body) if n.type == "enhanced_for_statement"):
            iterable = loop.child_by_field_name("value")
            loop_body = loop.child_by_field_name("body")
            if iterable is None or loop_body is None or iterable.type != "identifier":
                continue
            name = view.text(iterable)
            if base_name(view.context.scope.get(name, "")) not in jdk_costs.COLLECTIONS:
                continue
            for call in (n for n in cst.walk(loop_body) if n.type == "method_invocation"):
                receiver = call.child_by_field_name("object")
                method = view.text(call.child_by_field_name("name"))
                if receiver is None or view.text(receiver) != name or method not in _MUTATORS:
                    continue
                statement = view.statement_of(call)
                if _leaves_loop_after(statement):
                    continue
                start, end = view.lines(statement)
                found.append(
                    Finding(
                        id=ctx.unique_id("BUG-09", view.fid(statement)),
                        rule_id="BUG-09",
                        severity="high",
                        category="BUG",
                        title="Изменение коллекции во время обхода",
                        location=FindingLocation(
                            view.file, start, end, view.fid(statement), member.id
                        ),
                        explanation=(
                            f"`{view.text(call)}` меняет `{name}` внутри `for each` по этой же коллекции: "
                            "итератор обнаружит изменение и бросит `ConcurrentModificationException`."
                        ),
                        defect="Структурное изменение коллекции во время итерации.",
                        risk="Исключение на втором и последующих проходах или пропуск элементов.",
                        recommendation="Использовать итератор с `remove()`, `removeIf` либо собирать изменения в отдельный список.",
                        evidence=Evidence(
                            static=[
                                EvidenceItem("loop", f"for each по {name}", view.fid(loop)),
                                EvidenceItem("call", view.text(call), view.fid(statement)),
                            ]
                        ),
                    )
                )
    return found


# --- BUG-10: switch без default и «провалы» -----------------------------------------------------------------------


def rule_bug_10(ctx: AnalysisContext) -> list[Finding]:
    found: list[Finding] = []
    for member in _members(ctx):
        view = MemberView(ctx.project, ctx.model, member)
        body = view.body()
        if body is None:
            continue
        switches = (
            n
            for n in cst.walk(body)
            if n.type in {"switch_statement", "switch_expression"}
            and n.parent is not None
            and n.parent.type
            == "block"  # switch как оператор, а не выражение (там исчерпанность проверяет javac)
        )
        for node in switches:
            block = node.child_by_field_name("body")
            if block is None:
                continue
            groups = cst.named_children(block)
            has_default = any(
                (label.text or b"").strip().startswith(b"default")
                for group in groups
                for label in cst.children_of_type(group, "switch_label")
            )
            problems: list[str] = []
            if not has_default:
                problems.append("нет ветки `default`")
            for group in groups[:-1]:
                if group.type != "switch_block_statement_group":
                    continue
                statements = [c for c in cst.named_children(group) if c.type != "switch_label"]
                if statements and statements[-1].type not in {
                    "break_statement",
                    "return_statement",
                    "throw_statement",
                    "continue_statement",
                    "yield_statement",
                }:
                    problems.append("ветка «проваливается» в следующую без `break`")
                    break
            if not problems:
                continue
            start, end = view.lines(node)
            found.append(
                Finding(
                    id=ctx.unique_id("BUG-10", view.fid(node)),
                    rule_id="BUG-10",
                    severity="medium" if "проваливается" in " ".join(problems) else "low",
                    category="BUG",
                    title="Незавершённая ветвь `switch`",
                    location=FindingLocation(view.file, start, end, view.fid(node), member.id),
                    explanation="В `switch`: " + "; ".join(problems) + ".",
                    defect="Необработанное значение селектора или непреднамеренный провал в следующую ветвь.",
                    risk="Неожиданные значения молча игнорируются, а лишний код выполняется.",
                    recommendation="Добавить `default` и завершать каждую ветвь `break`/`return` (или перейти на стрелочный `switch`).",
                    evidence=Evidence(
                        static=[
                            EvidenceItem(
                                "switch",
                                view.text(node.child_by_field_name("condition")),
                                view.fid(node),
                            )
                        ]
                    ),
                )
            )
    return found


# --- MAINT-06: магические числа и строки --------------------------------------------------------------------------


def rule_maint_06(ctx: AnalysisContext) -> list[Finding]:
    found: list[Finding] = []
    for decl in ctx.project.types():
        file = decl.id.split("#", 1)[0]
        parsed = ctx.project.parsed(file)
        occurrences: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
        for member in decl.members:
            if member.kind not in FLOWABLE:
                continue
            body = ctx.project.context(member)[1]
            if body is None:
                continue
            for node in cst.walk(body):
                if node.type in _NUMBER:
                    text = parsed.text(node)
                    kind = "число"
                    if text in _ALLOWED_NUMBERS or _in_case_label(node) or _in_annotation(node):
                        continue
                elif node.type == "string_literal":
                    text = parsed.text(node)
                    if len(text) < 6 or _in_case_label(node) or _in_annotation(node):
                        continue
                    kind = "строка"
                else:
                    continue
                span = parsed.range_of(node)
                occurrences[(kind, text)].append((span.start.line, span.end.line))
        for (kind, text), places in sorted(occurrences.items(), key=lambda item: item[1][0]):
            needed = 2 if kind == "число" else 3
            if len(places) < needed:
                continue
            first = places[0]
            found.append(
                Finding(
                    id=ctx.unique_id("MAINT-06", f"{decl.id}/{text}"),
                    rule_id="MAINT-06",
                    severity="low",
                    category="MAINT",
                    title=f"Магическое значение {text}",
                    location=FindingLocation(file, first[0], first[1], decl.id, None),
                    explanation=f"{kind.capitalize()} {text} встречается {len(places)} раз в {decl.path} без имени.",
                    defect="Значение без смысла: непонятно, что оно означает и где его менять.",
                    risk="При изменении легко поправить одно вхождение и забыть остальные.",
                    recommendation=f"Вынести в именованную константу (`static final`) и использовать её во всех {len(places)} местах.",
                    evidence=Evidence(
                        static=[EvidenceItem("literal", f"{text} × {len(places)}", decl.id)]
                    ),
                )
            )
    return found


def _in_case_label(node: Node) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.type == "switch_label":
            return True
        if parent.type in {"block", "method_declaration"}:
            return False
        parent = parent.parent
    return False


def _in_annotation(node: Node) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.type in {"annotation", "marker_annotation"}:
            return True
        parent = parent.parent
    return False


# --- MAINT-07: неиспользуемые элементы -----------------------------------------------------------------------------


def rule_maint_07(ctx: AnalysisContext) -> list[Finding]:
    found: list[Finding] = []
    project = ctx.project
    called: Counter[str] = Counter()
    field_uses: Counter[str] = Counter()
    for member in project.members():
        if member.kind in FLOWABLE:
            called.update(project.call_counts(member))
            field_uses.update(project.use_counts(member)[0])
        elif member.kind == "field":
            # поля, читаемые в инициализаторах других полей
            pass
    text_by_file = {path: text for path, text in project.files.items()}
    for decl in project.types():
        file = decl.id.split("#", 1)[0]
        for member in decl.members:
            if "private" not in member.modifiers:
                continue
            if member.kind == "method" and member.name != "main" and called[member.id] == 0:
                found.append(_unused(ctx, member, file, "Неиспользуемый приватный метод", "метод"))
            elif member.kind == "field" and field_uses[member.id] == 0:
                usages = len(re.findall(rf"\b{re.escape(member.name)}\b", text_by_file[file]))
                if usages <= 1:
                    found.append(
                        _unused(ctx, member, file, "Неиспользуемое приватное поле", "поле")
                    )
    for member in _members(ctx):
        view = MemberView(ctx.project, ctx.model, member)
        body = view.body()
        if body is None:
            continue
        for node in (n for n in cst.walk(body) if n.type == "local_variable_declaration"):
            for declarator in cst.children_of_type(node, "variable_declarator"):
                name = view.text(declarator.child_by_field_name("name"))
                if name and not view.references_of(name, body):
                    start, end = view.lines(node)
                    found.append(
                        Finding(
                            id=ctx.unique_id("MAINT-07", f"{view.fid(node)}/{name}"),
                            rule_id="MAINT-07",
                            severity="low",
                            category="MAINT",
                            title=f"Неиспользуемая переменная {name}",
                            location=FindingLocation(
                                view.file, start, end, view.fid(node), member.id
                            ),
                            explanation=f"Локальная переменная `{name}` объявлена в {member.name}(), но нигде не читается.",
                            defect="Лишний код.",
                            risk="Читатель ищет смысл там, где его нет; возможна забытая логика.",
                            recommendation="Удалить переменную или использовать её значение.",
                            evidence=Evidence(
                                static=[EvidenceItem("variable", name, view.fid(node))]
                            ),
                        )
                    )
    return found


def _unused(ctx: AnalysisContext, member: Member, file: str, title: str, noun: str) -> Finding:
    project = ctx.project
    span = project.parsed(file).lines.range(member.start_byte, member.end_byte)
    return Finding(
        id=ctx.unique_id("MAINT-07", member.id),
        rule_id="MAINT-07",
        severity="low",
        category="MAINT",
        title=f"{title} {member.name}",
        location=FindingLocation(
            file,
            span.start.line,
            span.end.line,
            member.id,
            member.id if member.kind == "method" else None,
        ),
        explanation=f"Приватный {noun} `{member.name}` нигде не используется в проекте.",
        defect="Мёртвый код.",
        risk="Лишний код усложняет чтение и поддержку.",
        recommendation=f"Удалить {noun} или начать использовать.",
        evidence=Evidence(static=[EvidenceItem("member", member.key, member.id)]),
    )


# --- MAINT-10: именование --------------------------------------------------------------------------------------------


def rule_maint_10(ctx: AnalysisContext) -> list[Finding]:
    found: list[Finding] = []
    for decl in ctx.project.types():
        file = decl.id.split("#", 1)[0]
        span_of = ctx.project.parsed(file).lines
        if not _PASCAL_TYPE.match(decl.name):
            span = span_of.range(decl.start_byte, decl.end_byte)
            found.append(
                _naming(
                    ctx,
                    decl.id,
                    file,
                    span.start.line,
                    span.end.line,
                    f"Тип `{decl.name}`",
                    "PascalCase",
                )
            )
        for member in decl.members:
            if member.kind == "method" and not _CAMEL_METHOD.match(member.name):
                span = span_of.range(member.start_byte, member.end_byte)
                found.append(
                    _naming(
                        ctx,
                        member.id,
                        file,
                        span.start.line,
                        span.end.line,
                        f"Метод `{member.name}`",
                        "camelCase",
                    )
                )
            elif (
                member.kind == "field"
                and member.role == "field"
                and member.name != "serialVersionUID"
            ):
                constant = "static" in member.modifiers and "final" in member.modifiers
                if not (
                    _CONSTANT.match(member.name) if constant else _CAMEL_METHOD.match(member.name)
                ):
                    span = span_of.range(member.start_byte, member.end_byte)
                    expected = "UPPER_SNAKE_CASE" if constant else "camelCase"
                    found.append(
                        _naming(
                            ctx,
                            member.id,
                            file,
                            span.start.line,
                            span.end.line,
                            f"Поле `{member.name}`",
                            expected,
                        )
                    )
    return found


def _naming(
    ctx: AnalysisContext, node_id: str, file: str, start: int, end: int, subject: str, expected: str
) -> Finding:
    return Finding(
        id=ctx.unique_id("MAINT-10", node_id),
        rule_id="MAINT-10",
        severity="low",
        category="MAINT",
        title=f"Имя не по соглашению: {subject.split('`')[1]}",
        location=FindingLocation(file, start, end, node_id, None),
        explanation=f"{subject} не соответствует соглашению Java ({expected}).",
        defect="Нарушение соглашения об именовании.",
        risk="Код выглядит чужеродно, а инструменты и коллеги путаются в видах символов.",
        recommendation=f"Переименовать в стиле {expected} (операция `rename_symbol` обновит все использования).",
        evidence=Evidence(static=[EvidenceItem("name", subject, node_id)]),
    )


RULES_EXTRA = (
    rule_perf_04,
    rule_perf_08,
    rule_bug_07,
    rule_bug_09,
    rule_bug_10,
    rule_maint_06,
    rule_maint_07,
    rule_maint_10,
)
