"""Эталон и сравнение поведения (docs/07 § 4): наблюдение за запуском, классификация, вердикты."""

from __future__ import annotations

import difflib
from collections.abc import Sequence
from dataclasses import dataclass, field

from engine.runtime.runner import RunResult
from engine.verify.normalize import (
    Mask,
    exception_summary,
    normalize_stderr,
    normalize_stdout,
    suggest_masks,
)


@dataclass(frozen=True, slots=True)
class Observed:
    """Нормализованное поведение программы на сценарии."""

    stdout: str
    stderr: str
    exit_code: int | None
    exception: str | None  # «Тип: сообщение»
    duration_ms: int = 0

    def same_behavior(self, other: Observed) -> bool:
        return (self.stdout, self.stderr, self.exit_code, self.exception) == (
            other.stdout,
            other.stderr,
            other.exit_code,
            other.exception,
        )


@dataclass(frozen=True, slots=True)
class TextChange:
    expected: str
    actual: str
    unified: str


@dataclass(frozen=True, slots=True)
class ValueChange:
    expected: object
    actual: object


@dataclass(slots=True)
class Difference:
    stdout: TextChange | None = None
    stderr: TextChange | None = None
    exit_code: ValueChange | None = None
    exception: ValueChange | None = None

    def __bool__(self) -> bool:
        return any((self.stdout, self.stderr, self.exit_code, self.exception))


def observe(result: RunResult, masks: Sequence[Mask] = (), *, strip_ws: bool = False) -> Observed:
    exception = result.exception
    return Observed(
        stdout=normalize_stdout(result.stdout, masks, strip_trailing_ws=strip_ws),
        stderr=normalize_stderr(result.stderr, masks),
        exit_code=result.exit_code,
        exception=exception_summary(exception.type, exception.message) if exception else None,
        duration_ms=result.duration_ms,
    )


def _text_change(expected: str, actual: str) -> TextChange | None:
    if expected == actual:
        return None
    unified = "".join(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile="эталон",
            tofile="фактически",
        )
    )
    return TextChange(expected, actual, unified)


def differences(expected: Observed, actual: Observed) -> Difference:
    return Difference(
        stdout=_text_change(expected.stdout, actual.stdout),
        stderr=_text_change(expected.stderr, actual.stderr),
        exit_code=(
            ValueChange(expected.exit_code, actual.exit_code)
            if expected.exit_code != actual.exit_code
            else None
        ),
        exception=(
            ValueChange(expected.exception, actual.exception)
            if expected.exception != actual.exception
            else None
        ),
    )


def verdict(
    result: RunResult, expected: Observed, actual: Observed
) -> tuple[str, Difference | None]:
    """``PASS``/``FAIL``/``ERROR``/``TIMEOUT`` (docs/07 § 4.2) и различия для ``FAIL``."""
    if result.status == "timeout":
        return "TIMEOUT", None
    if result.status in {"internal", "output_limit", "cancelled"}:
        return "ERROR", None
    diff = differences(expected, actual)
    return ("FAIL", diff) if diff else ("PASS", None)


# --- запись эталона (двойной прогон) ------------------------------------------------------------------


@dataclass(slots=True)
class Classification:
    """Итог двойного прогона сценария при записи эталона."""

    stability: str  # stable | masked | nondeterministic
    masks: list[Mask]
    baseline: Observed
    warnings: list[str] = field(default_factory=list)


def classify(
    first: RunResult,
    second: RunResult,
    masks: Sequence[Mask] = (),
    *,
    strip_ws: bool = False,
) -> Classification:
    """Совпали ли два прогона; при расхождении подбираются маски (docs/07 § 3.3)."""
    a = observe(first, masks, strip_ws=strip_ws)
    b = observe(second, masks, strip_ws=strip_ws)
    base = Observed(a.stdout, a.stderr, a.exit_code, a.exception, min(a.duration_ms, b.duration_ms))
    if first.status in {"timeout", "internal", "output_limit"} or second.status in {
        "timeout",
        "internal",
        "output_limit",
    }:
        reason = "превышено время" if "timeout" in {first.status, second.status} else "сбой запуска"
        return Classification(
            "nondeterministic", list(masks), base, [f"эталон не записан: {reason}"]
        )
    if a.same_behavior(b):
        return Classification("masked" if masks else "stable", list(masks), base)

    proposed = suggest_masks(first.stdout, second.stdout, masks)
    stderr_proposed = suggest_masks(first.stderr, second.stderr, [*masks, *proposed])
    all_masks = [*masks, *proposed, *stderr_proposed]
    if proposed or stderr_proposed:
        a2 = observe(first, all_masks, strip_ws=strip_ws)
        b2 = observe(second, all_masks, strip_ws=strip_ws)
        if a2.same_behavior(b2):
            base = Observed(
                a2.stdout,
                a2.stderr,
                a2.exit_code,
                a2.exception,
                min(a2.duration_ms, b2.duration_ms),
            )
            return Classification(
                "masked", all_masks, base, ["нестабильные фрагменты замаскированы автоматически"]
            )
    return Classification(
        "nondeterministic",
        list(masks),
        base,
        ["два прогона дали разный вывод: сценарий исключён из проверки"],
    )
