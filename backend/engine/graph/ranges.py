"""Координаты в тексте: байтовые смещения tree-sitter ↔ строки и колонки Monaco.

Внутри engine все диапазоны — байтовые смещения UTF-8. На границе API они переводятся в
``Position``: строка с 1, колонка с 1 в единицах UTF-16 (как в Monaco), иначе кириллица и
эмодзи сдвигают подсветку.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class Position:
    line: int  # с 1
    column: int  # с 1, в единицах UTF-16


@dataclass(frozen=True, slots=True)
class SourceRange:
    start: Position
    end: Position


def _utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


class LineIndex:
    """Индекс начал строк для перевода байтовых смещений в ``Position`` и обратно."""

    def __init__(self, source: bytes) -> None:
        self._source = source
        starts = [0]
        for i, byte in enumerate(source):
            if byte == 0x0A:  # \n; для CRLF символ \r остаётся в конце предыдущей строки
                starts.append(i + 1)
        self._starts = starts

    @property
    def line_count(self) -> int:
        return len(self._starts)

    def position(self, offset: int) -> Position:
        """Байтовое смещение → строка и UTF-16-колонка (обе с 1)."""
        offset = max(0, min(offset, len(self._source)))
        line_idx = bisect_right(self._starts, offset) - 1
        prefix = self._source[self._starts[line_idx] : offset]
        return Position(line_idx + 1, _utf16_len(prefix.decode("utf-8", errors="replace")) + 1)

    def range(self, start: int, end: int) -> SourceRange:
        return SourceRange(self.position(start), self.position(end))

    def offset(self, position: Position) -> int:
        """Строка и UTF-16-колонка → байтовое смещение (обратное преобразование)."""
        line_idx = min(max(position.line, 1), len(self._starts)) - 1
        line_start = self._starts[line_idx]
        if line_idx + 1 < len(self._starts):
            line_end = self._starts[line_idx + 1]
        else:
            line_end = len(self._source)
        line_text = self._source[line_start:line_end].decode("utf-8", errors="replace")
        target_units = position.column - 1
        units = 0
        consumed = 0
        for ch in line_text:
            if units >= target_units:
                break
            units += _utf16_len(ch)
            consumed += len(ch.encode("utf-8"))
        return line_start + consumed
