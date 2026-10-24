"""Представление сложности Big O: пара степеней ``(n, log n)`` и признак экспоненты (docs/05 § 3.1)."""

from __future__ import annotations

from dataclasses import dataclass

_SUPERSCRIPT = {1: "", 2: "²", 3: "³", 4: "⁴", 5: "⁵"}


@dataclass(frozen=True, slots=True, order=True)
class Cost:
    """``n^p · log^q n``; ``exp`` — экспоненциальная (перекрывает остальное)."""

    exp: bool = False
    n: int = 0
    log: int = 0

    def __add__(self, other: Cost) -> Cost:
        """Последовательность: доминирующая стоимость."""
        return max(self, other)

    def __mul__(self, other: Cost) -> Cost:
        """Вложение: степени складываются."""
        if self.exp or other.exp:
            return EXP
        return Cost(False, self.n + other.n, self.log + other.log)

    @property
    def is_constant(self) -> bool:
        return not self.exp and self.n == 0 and self.log == 0

    def factor(self) -> str:
        """Выражение без ``O(…)``: ``n²``, ``n log n``, ``log n``, ``1``."""
        if self.exp:
            return "2ⁿ"
        parts: list[str] = []
        if self.n:
            parts.append("n" + _SUPERSCRIPT.get(self.n, f"^{self.n}"))
        if self.log:
            parts.append("log n" if self.log == 1 else f"log{_SUPERSCRIPT.get(self.log, '')} n")
        return " ".join(parts) or "1"

    def format(self) -> str:
        return f"O({self.factor()})"

    @property
    def degree(self) -> float:
        """Эмпирическая степень роста для сравнения со степенью ``k`` из бенчмарка."""
        return float(self.n) + (0.1 * self.log if self.log else 0.0)


ONE = Cost()
LOGN = Cost(False, 0, 1)
N = Cost(False, 1, 0)
NLOGN = Cost(False, 1, 1)
N2 = Cost(False, 2, 0)
EXP = Cost(True, 0, 0)
