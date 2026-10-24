"""Метрики кода и поиск клонов (S7.3, docs/05 § 4): LOC, цикломатика, вложенность, LCOM4, дубли."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from tree_sitter import Node

from engine.analysis.cost_model import CostModel
from engine.java import cst
from engine.java.project import FLOWABLE, JavaProject
from engine.java.symbols import Member, TypeDecl

CLONE_MIN_STATEMENTS = (
    5  # минимальный размер клона в операторах с вложенными (docs/05 § 5.3, MAINT-02)
)
CLONE_MIN_CHARS = 60  # и в знаках нормализованного текста: ``i++; j++;`` клоном не считается
CLONE_MAX_WINDOW = 12  # длиннейшая проверяемая последовательность соседних операторов

_LITERALS = {
    "decimal_integer_literal": "NUM",
    "hex_integer_literal": "NUM",
    "octal_integer_literal": "NUM",
    "binary_integer_literal": "NUM",
    "decimal_floating_point_literal": "NUM",
    "hex_floating_point_literal": "NUM",
    "string_literal": "STR",
    "character_literal": "CHR",
    "true": "BOOL",
    "false": "BOOL",
    "null_literal": "NULL",
}
_IDENTIFIERS = {"identifier", "type_identifier"}
_BRANCHES = {
    "if_statement",
    "for_statement",
    "enhanced_for_statement",
    "while_statement",
    "do_statement",
    "catch_clause",
    "ternary_expression",
}
_NESTING = {
    "if_statement",
    "for_statement",
    "enhanced_for_statement",
    "while_statement",
    "do_statement",
    "switch_statement",
    "switch_expression",
    "try_statement",
    "try_with_resources_statement",
    "synchronized_statement",
    "catch_clause",
}


@dataclass(slots=True)
class MethodMetrics:
    method_id: str
    name: str
    file: str
    lines: int
    cyclomatic: int
    cognitive: int
    max_nesting: int
    params: int
    complexity: str | None = None


@dataclass(slots=True)
class TypeMetrics:
    type_id: str
    name: str
    file: str
    lines: int
    methods: int
    fields: int
    lcom4: float


@dataclass(slots=True)
class MetricsTotals:
    lines: int
    code_lines: int
    files: int
    types: int
    methods: int
    cyclomatic_avg: float
    cyclomatic_max: int
    duplication_percent: float
    lcom4_avg: float


@dataclass(slots=True)
class Metrics:
    totals: MetricsTotals
    methods: list[MethodMetrics]
    types: list[TypeMetrics]


@dataclass(frozen=True, slots=True)
class Place:
    file: str
    method_id: str
    start_line: int
    end_line: int
    first: int  # индекс первого оператора в списке-родителе
    owner: int  # номер списка операторов (для проверки пересечения)
    size: int  # сколько соседних операторов в окне
    weight: int  # сколько операторов вместе с вложенными


@dataclass(slots=True)
class Clone:
    """Два одинаковых (с точностью до имён и литералов) участка из ``statements`` операторов."""

    first: Place
    second: Place
    statements: int


@dataclass(slots=True)
class MetricsResult:
    metrics: Metrics
    clones: list[Clone] = field(default_factory=list)


# --- строки -----------------------------------------------------------------------------------------


def code_line_flags(lines: list[str]) -> list[bool]:
    """Для каждой строки: есть ли в ней код (не пустая и не только комментарий)."""
    flags: list[bool] = []
    in_block = False
    for raw in lines:
        text = raw.strip()
        code = False
        while text:
            if in_block:
                end = text.find("*/")
                if end < 0:
                    text = ""
                else:
                    in_block, text = False, text[end + 2 :].strip()
            elif text.startswith("//"):
                text = ""
            elif text.startswith("/*"):
                in_block, text = True, text[2:]
            else:
                code, text = True, ""
        flags.append(code)
    return flags


def _count(flags: list[bool], start_line: int, end_line: int) -> int:
    return sum(flags[start_line - 1 : end_line])


# --- обход метода -------------------------------------------------------------------------------------


def _operator(node: Node) -> str:
    operator = node.child_by_field_name("operator")
    return operator.type if operator is not None else ""


def cyclomatic(body: Node) -> int:
    total = 1
    for node in cst.walk(body):
        kind = node.type
        if kind in _BRANCHES or kind == "binary_expression" and _operator(node) in {"&&", "||"}:
            total += 1
        elif kind == "switch_block":
            total += sum(_case_labels_in_group(group) for group in cst.named_children(node))
    return total


def _case_labels_in_group(group: Node) -> int:
    """Метки ``case`` группы (``default`` не добавляет путь выполнения)."""
    labels = cst.children_of_type(group, "switch_label")
    return len(
        [label for label in labels if not (label.text or b"").strip().startswith(b"default")]
    )


def nesting_and_cognitive(body: Node) -> tuple[int, int]:
    """``(максимальная вложенность, когнитивная сложность)`` без рекурсии по Python-стеку."""
    deepest = 0
    cognitive = 0
    stack: list[tuple[Node, int]] = [(body, 0)]
    while stack:
        node, depth = stack.pop()
        kind = node.type
        child_depth = depth
        if kind in _NESTING:
            is_else_if = (
                kind == "if_statement"
                and node.parent is not None
                and node.parent.type == "if_statement"
                and node.parent.child_by_field_name("alternative") is not None
                and node.parent.child_by_field_name("alternative").id == node.id  # type: ignore[union-attr]
            )
            if is_else_if:
                cognitive += 1
            else:
                cognitive += 1 + depth
                child_depth = depth + 1
                deepest = max(deepest, child_depth)
        elif kind == "binary_expression" and _operator(node) in {"&&", "||"}:
            parent = node.parent
            if (
                parent is None
                or parent.type != "binary_expression"
                or _operator(parent) != _operator(node)
            ):
                cognitive += 1
        elif kind in {"lambda_expression"}:
            child_depth = depth + 1
        for child in node.children:
            stack.append((child, child_depth))
    return deepest, cognitive


# --- клоны -----------------------------------------------------------------------------------------------


def _tokens(node: Node, out: list[str]) -> None:
    kind = node.type
    if kind in {"line_comment", "block_comment"}:
        return
    if kind in _LITERALS:
        out.append(_LITERALS[kind])
        return
    if kind in _IDENTIFIERS:
        out.append("ID")
        return
    if not node.children:
        out.append(node.type)
        return
    for child in node.children:
        _tokens(child, out)


def _statement_count(node: Node) -> int:
    """Число операторов в поддереве (сам оператор и вложенные)."""
    return sum(
        1
        for item in cst.walk(node)
        if item.type.endswith("_statement") or item.type == "local_variable_declaration"
    )


def normalized(node: Node) -> str:
    out: list[str] = []
    _tokens(node, out)
    return " ".join(out)


# --- метрики проекта ---------------------------------------------------------------------------------------


class MetricsBuilder:
    def __init__(self, project: JavaProject, model: CostModel) -> None:
        self.project = project
        self.model = model
        self._flags: dict[str, list[bool]] = {}

    def flags(self, path: str) -> list[bool]:
        if path not in self._flags:
            self._flags[path] = code_line_flags(self.project.files[path].split("\n"))
        return self._flags[path]

    def build(self) -> MetricsResult:
        project = self.project
        methods: list[MethodMetrics] = []
        windows: dict[tuple[str, ...], list[Place]] = defaultdict(list)
        owner_counter = 0
        for member in project.members():
            if member.kind not in FLOWABLE:
                continue
            path = project.file_of(member)
            ctx, declaration = project.context(member)
            span = project.parsed(path).lines.range(member.start_byte, member.end_byte)
            body = None
            if declaration is not None:
                body = declaration.child_by_field_name("body") or cst.first_child_of_type(
                    declaration, "block"
                )
            if body is None:
                continue
            nesting, cognitive = nesting_and_cognitive(body)
            found = self.model.method(member.id)
            methods.append(
                MethodMetrics(
                    method_id=member.id,
                    name=member.name,
                    file=path,
                    lines=_count(self.flags(path), span.start.line, span.end.line),
                    cyclomatic=cyclomatic(body),
                    cognitive=cognitive,
                    max_nesting=nesting,
                    params=len(member.params),
                    complexity=found.cost.format() if found is not None else None,
                )
            )
            owner_counter = self._collect_windows(
                project, member, path, body, windows, owner_counter
            )

        clones = self._clones(windows)
        types = [self._type_metrics(decl) for decl in project.types()]
        return MetricsResult(Metrics(self._totals(methods, types, clones), methods, types), clones)

    # --- клоны ----------------------------------------------------------------------------------------------

    def _collect_windows(
        self,
        project: JavaProject,
        member: Member,
        path: str,
        body: Node,
        windows: dict[tuple[str, ...], list[Place]],
        owner_counter: int,
    ) -> int:
        """Окна из соседних операторов блока: клон — не меньше ``CLONE_MIN_STATEMENTS`` операторов
        (с вложенными) и ``CLONE_MIN_CHARS`` знаков нормализованного текста."""
        parsed = project.parsed(path)
        for block in cst.walk(body):
            if block.type != "block":
                continue
            statements = cst.named_children(block)
            owner_counter += 1
            if len(statements) < 2:
                continue
            texts = [normalized(s) for s in statements]
            weights = [_statement_count(s) for s in statements]
            spans = [parsed.range_of(s) for s in statements]
            for size in range(2, min(len(statements), CLONE_MAX_WINDOW) + 1):
                for index in range(len(statements) - size + 1):
                    key = tuple(texts[index : index + size])
                    weight = sum(weights[index : index + size])
                    if weight < CLONE_MIN_STATEMENTS or sum(len(t) for t in key) < CLONE_MIN_CHARS:
                        continue
                    if len(set(key)) < 2:
                        continue  # одинаковые операторы подряд (``n += 1; n += 2; …``) — не клон
                    windows[key].append(
                        Place(
                            path,
                            member.id,
                            spans[index].start.line,
                            spans[index + size - 1].end.line,
                            index,
                            owner_counter,
                            size,
                            weight,
                        )
                    )
        return owner_counter

    def _clones(self, windows: dict[tuple[str, ...], list[Place]]) -> list[Clone]:
        """Самые длинные повторы; окно, целиком лежащее в уже принятом, отбрасывается."""
        accepted: dict[int, list[tuple[int, int]]] = defaultdict(list)  # owner → [start, end)
        found: list[Clone] = []
        ordered = sorted(
            (places for places in windows.values() if len(places) >= 2),
            key=lambda places: (
                -places[0].weight,
                places[0].file,
                places[0].owner,
                places[0].first,
            ),
        )
        for places in ordered:
            first = places[0]
            for other in places[1:]:
                if first.owner == other.owner and abs(first.first - other.first) < first.size:
                    continue
                if self._inside(accepted, first) and self._inside(accepted, other):
                    continue
                found.append(Clone(first, other, first.weight))
                accepted[first.owner].append((first.first, first.first + first.size))
                accepted[other.owner].append((other.first, other.first + other.size))
        found.sort(
            key=lambda c: (c.first.file, c.first.start_line, c.second.file, c.second.start_line)
        )
        return found

    @staticmethod
    def _inside(accepted: dict[int, list[tuple[int, int]]], place: Place) -> bool:
        end = place.first + place.size
        return any(lo <= place.first and end <= hi for lo, hi in accepted[place.owner])

    # --- типы ------------------------------------------------------------------------------------------------

    def _type_metrics(self, decl: TypeDecl) -> TypeMetrics:
        project = self.project
        path = decl.id.split("#", 1)[0]
        span = project.parsed(path).lines.range(decl.start_byte, decl.end_byte)
        return TypeMetrics(
            type_id=decl.id,
            name=decl.path,
            file=path,
            lines=_count(self.flags(path), span.start.line, span.end.line),
            methods=sum(1 for m in decl.members if m.kind in {"method", "constructor"}),
            fields=sum(1 for m in decl.members if m.kind == "field"),
            lcom4=self.lcom4(decl),
        )

    def _trivial(self, member: Member) -> bool:
        """Геттер/сеттер/делегат (не больше одного оператора) не отражает связность класса."""
        _, declaration = self.project.context(member)
        if declaration is None:
            return False
        body = declaration.child_by_field_name("body") or cst.first_child_of_type(
            declaration, "block"
        )
        return body is not None and len(cst.named_children(body)) <= 1

    def lcom4(self, decl: TypeDecl) -> float:
        """Число компонент связности графа «методы — используемые поля и вызовы внутри класса»."""
        if decl.kind == "interface":
            return 0.0
        methods = [
            m
            for m in decl.members
            if m.kind == "method" and not m.is_static and not self._trivial(m)
        ]
        if not methods:
            return 0.0
        parent: dict[str, str] = {}

        def find(x: str) -> str:
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            parent[find(a)] = find(b)

        own_fields = {m.id for m in decl.members if m.kind == "field"}
        own_methods = {m.id for m in methods}
        for method in methods:
            find(method.id)
            used_fields, _ = self.project.use_counts(method)
            for field_id in used_fields:
                if field_id in own_fields:
                    union(method.id, field_id)
            for callee in self.project.call_counts(method):
                if callee in own_methods:
                    union(method.id, callee)
        return float(len({find(m.id) for m in methods}))

    # --- итоги ------------------------------------------------------------------------------------------------

    def _totals(
        self, methods: list[MethodMetrics], types: list[TypeMetrics], clones: list[Clone]
    ) -> MetricsTotals:
        project = self.project
        total_lines = sum(
            len(text.split("\n")) - (1 if text.endswith("\n") else 0)
            for text in project.files.values()
        )
        code = sum(sum(self.flags(path)) for path in project.files)
        duplicated: set[tuple[str, int]] = set()
        for clone in clones:
            for place in (clone.first, clone.second):
                flags = self.flags(place.file)
                for line in range(place.start_line, place.end_line + 1):
                    if flags[line - 1]:
                        duplicated.add((place.file, line))
        cyclomatics = [m.cyclomatic for m in methods]
        lcoms = [t.lcom4 for t in types if t.methods and t.lcom4 > 0]
        return MetricsTotals(
            lines=total_lines,
            code_lines=code,
            files=len(project.files),
            types=len(types),
            methods=len(methods),
            cyclomatic_avg=round(sum(cyclomatics) / len(cyclomatics), 2) if cyclomatics else 0.0,
            cyclomatic_max=max(cyclomatics, default=0),
            duplication_percent=round(100 * len(duplicated) / code, 1) if code else 0.0,
            lcom4_avg=round(sum(lcoms) / len(lcoms), 2) if lcoms else 0.0,
        )


def compute_metrics(project: JavaProject, model: CostModel) -> MetricsResult:
    return MetricsBuilder(project, model).build()
