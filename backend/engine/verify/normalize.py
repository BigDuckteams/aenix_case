"""Нормализация вывода перед сравнением (docs/07 § 3.2) и подбор масок для нестабильных фрагментов."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

_STACK_PREFIXES = ("\tat ", "\t... ", "Picked up ")


@dataclass(frozen=True, slots=True)
class Mask:
    pattern: str
    replacement: str


def eol(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def apply_masks(text: str, masks: Sequence[Mask]) -> str:
    for mask in masks:
        try:
            text = re.sub(mask.pattern, mask.replacement, text)
        except re.error:
            continue  # битая маска не должна ронять сравнение
    return text


def normalize_stdout(
    text: str,
    masks: Sequence[Mask] = (),
    *,
    strip_trailing_ws: bool = False,
    strip_trailing_blank: bool = True,
) -> str:
    """LF, маски, (опционально) хвостовые пробелы строк и пустые строки в конце."""
    text = eol(text)
    if strip_trailing_ws:
        text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = apply_masks(text, masks)
    return text.rstrip("\n") if strip_trailing_blank else text


def normalize_stderr(text: str, masks: Sequence[Mask] = ()) -> str:
    """Из стека исключения остаются тип и сообщение: кадры ``at …`` зависят от строк кода."""
    kept = [
        line
        for line in eol(text).split("\n")
        if line.strip() and not line.startswith(_STACK_PREFIXES)
    ]
    return apply_masks("\n".join(kept), masks)


def exception_summary(type_name: str | None, message: str | None) -> str | None:
    if not type_name:
        return None
    return f"{type_name}: {message}" if message else type_name


# --- подбор масок ---------------------------------------------------------------------------------

# От частного к общему: первый шаблон, делающий строки равными, и выбирается.
_CANDIDATES: tuple[Mask, ...] = (
    Mask(r"@[0-9a-f]{4,}", "@<HASH>"),
    Mask(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<UUID>"),
    Mask(
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?", "<TIMESTAMP>"
    ),
    Mask(r"\d+(?:[.,]\d+)?\s?(?:ms|мс|ns|нс|µs|мкс)\b", "<TIME>"),
    Mask(r"\d+(?:[.,]\d+)?", "<NUM>"),
)


def suggest_masks(first: str, second: str, existing: Sequence[Mask] = ()) -> list[Mask]:
    """Маски, после которых два вывода одной и той же программы совпадают; пусто — не удалось."""
    a = apply_masks(eol(first), existing).split("\n")
    b = apply_masks(eol(second), existing).split("\n")
    if len(a) != len(b):
        return []
    chosen: list[Mask] = []
    for line_a, line_b in zip(a, b, strict=True):
        if line_a == line_b:
            continue
        for candidate in _CANDIDATES:
            if apply_masks(line_a, [*chosen, candidate]) == apply_masks(
                line_b, [*chosen, candidate]
            ):
                if candidate not in chosen:
                    chosen.append(candidate)
                break
        else:
            return []
    return chosen
