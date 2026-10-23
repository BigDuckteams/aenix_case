"""Структурные идентификаторы узлов (docs/04-code-graph-model.md § 5.3).

    {file}#{TypePath}.{memberKey}/{path}
    Main.java#Main.processOrders(List<Order>)/foreach[0]/if[0]/then/op[1]

ID не зависит от номеров строк, поэтому остаётся стабильным при вставке пустых строк и
комментариев выше. Номер в ``kind[i]`` — индекс среди однотипных соседей в одной цепочке.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Вид блока → имя сегмента пути.
PATH_NAMES: dict[str, str] = {
    "var_decl": "var",
    "assign": "assign",
    "operation": "op",
    "condition": "if",
    "switch": "switch",
    "case": "case",
    "loop_for": "for",
    "loop_foreach": "foreach",
    "loop_while": "while",
    "try": "try",
    "catch": "catch",
    "finally": "finally",
    "throw": "throw",
    "return": "return",
    "break": "break",
    "continue": "continue",
    "yield": "yield",
    "lambda": "lambda",
    "local_type": "local_type",
    "labeled": "labeled",
    "assert": "assert",
    "sync": "sync",
    "code": "code",
}


def type_id(file: str, type_path: str) -> str:
    return f"{file}#{type_path}"


def member_id(file: str, type_path: str, key: str) -> str:
    return f"{file}#{type_path}.{key}"


def split_node_id(node_id: str) -> tuple[str, tuple[str, ...]]:
    """``(id члена, сегменты пути)``: всё до первого ``/`` — член, дальше — путь внутри метода."""
    head, _, rest = node_id.partition("/")
    return head, tuple(rest.split("/")) if rest else ()


def node_depth(node_id: str) -> int:
    """Вложенность по пути: число сегментов ``kind[i]`` (ветви ``then``/``else`` не считаются)."""
    return sum(1 for segment in split_node_id(node_id)[1] if segment.endswith("]"))


@dataclass(slots=True)
class PathScope:
    """Счётчики однотипных соседей в одной цепочке операторов.

    Для каждой цепочки (тело метода, тело цикла, ветвь условия, секция try…) создаётся свой
    ``PathScope`` с префиксом пути: так индекс считается среди соседей, а не по всему методу.
    """

    prefix: str = ""
    _counts: dict[str, int] = field(default_factory=dict)

    def next(self, segment: str) -> str:
        index = self._counts.get(segment, 0)
        self._counts[segment] = index + 1
        return f"{self.prefix}{segment}[{index}]"

    def child(self, name: str) -> PathScope:
        """Новая цепочка внутри секции ``name`` (``then``, ``else``, ``body``…)."""
        return PathScope(prefix=f"{self.prefix}{name}/")

    def nested(self, own_segment: str) -> PathScope:
        """Цепочка внутри узла с путём ``own_segment`` (``foreach[0]/``)."""
        return PathScope(prefix=f"{own_segment}/")
