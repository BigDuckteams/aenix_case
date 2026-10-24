"""Нормализация, маски, сравнение и классификация эталона (S6.2, docs/07 § 3–4) без JDK."""

from __future__ import annotations

from engine.runtime.runner import ExceptionInfo, RunResult
from engine.verify import compare
from engine.verify.normalize import (
    Mask,
    apply_masks,
    exception_summary,
    normalize_stderr,
    normalize_stdout,
    suggest_masks,
)


def result(
    stdout: str = "",
    stderr: str = "",
    exit_code: int | None = 0,
    status: str = "ok",
    exception: ExceptionInfo | None = None,
    duration_ms: int = 10,
) -> RunResult:
    return RunResult(status, stdout, stderr, exit_code, exception, duration_ms)


# --- нормализация --------------------------------------------------------------------------------


def test_stdout_gets_lf_and_loses_trailing_newlines():
    assert normalize_stdout("a\r\nb\r\n\r\n") == "a\nb"
    assert normalize_stdout("a\rb") == "a\nb"
    assert normalize_stdout("a\n\n", strip_trailing_blank=False) == "a\n\n"


def test_trailing_spaces_are_kept_unless_requested():
    assert normalize_stdout("a  \nb \n") == "a  \nb "
    assert normalize_stdout("a  \nb \n", strip_trailing_ws=True) == "a\nb"


def test_stderr_keeps_exception_type_and_message_but_not_frames():
    stderr = (
        'Exception in thread "main" java.lang.IllegalStateException: boom\n'
        "\tat Main.run(Main.java:12)\n"
        "\tat Main.main(Main.java:5)\n"
        "Caused by: java.io.IOException: disk\n"
        "\t... 2 more\n"
        "Picked up JAVA_TOOL_OPTIONS: -Xmx1g\n"
    )
    assert normalize_stderr(stderr) == (
        'Exception in thread "main" java.lang.IllegalStateException: boom\n'
        "Caused by: java.io.IOException: disk"
    )


def test_stack_frames_with_different_line_numbers_do_not_matter():
    a = 'Exception in thread "main" java.lang.Error: x\n\tat A.f(A.java:1)\n'
    b = 'Exception in thread "main" java.lang.Error: x\n\tat A.f(A.java:99)\n\tat A.g(A.java:3)\n'
    assert normalize_stderr(a) == normalize_stderr(b)


def test_masks_replace_unstable_fragments_and_ignore_broken_patterns():
    masks = [Mask(r"\d+ мс", "<MS>"), Mask("(", "oops")]
    assert apply_masks("готово за 123 мс, ещё 7 мс", masks) == "готово за <MS>, ещё <MS>"


def test_exception_summary():
    assert exception_summary("java.lang.Error", "x") == "java.lang.Error: x"
    assert exception_summary("java.lang.Error", None) == "java.lang.Error"
    assert exception_summary(None, "x") is None


# --- подбор масок ---------------------------------------------------------------------------------


def test_masks_are_suggested_for_hashes_uuids_times_and_numbers():
    cases = {
        "obj Item@1b6d3586 done": "obj Item@7852e922 done",
        "id 3f2b8c1e-1111-4222-8333-444455556666": "id 9a8b7c6d-1111-4222-8333-444455556666",
        "took 12 ms": "took 345 ms",
        "2026-10-24 03:48:13 start": "2026-10-24 03:49:59 start",
        "value 0.123": "value 0.987",
    }
    for first, second in cases.items():
        masks = suggest_masks(first, second)
        assert masks, first
        assert apply_masks(first, masks) == apply_masks(second, masks)


def test_no_masks_when_text_differs_beyond_numbers():
    assert suggest_masks("hello", "world") == []
    assert suggest_masks("a\nb", "a") == []  # разное число строк


def test_identical_outputs_need_no_masks():
    assert suggest_masks("same 1", "same 1") == []


# --- сравнение -------------------------------------------------------------------------------------


def test_equal_behaviour_is_pass_and_different_stdout_is_fail_with_unified_diff():
    expected = compare.observe(result("a\nb\n"))
    assert compare.verdict(result("a\nb\r\n"), expected, compare.observe(result("a\nb\r\n"))) == (
        "PASS",
        None,
    )
    actual_result = result("a\nX\n")
    verdict, diff = compare.verdict(actual_result, expected, compare.observe(actual_result))
    assert verdict == "FAIL"
    assert diff is not None and diff.stdout is not None
    assert "-b" in diff.stdout.unified and "+X" in diff.stdout.unified
    assert diff.exit_code is None and diff.exception is None


def test_exit_code_and_exception_differences_are_reported():
    boom = ExceptionInfo("java.lang.IllegalStateException", "boom", ["at A.f(A.java:1)"])
    expected = compare.observe(result("ok\n", exit_code=0))
    actual_result = result("ok\n", stderr="x", exit_code=1, exception=boom)
    verdict, diff = compare.verdict(actual_result, expected, compare.observe(actual_result))
    assert verdict == "FAIL" and diff is not None
    assert (diff.exit_code.expected, diff.exit_code.actual) == (0, 1)  # type: ignore[union-attr]
    assert diff.exception.actual == "java.lang.IllegalStateException: boom"  # type: ignore[union-attr]
    assert diff.stderr is not None


def test_timeout_and_internal_errors_are_not_fail():
    expected = compare.observe(result("a"))
    slow = result("", status="timeout", exit_code=None)
    assert compare.verdict(slow, expected, compare.observe(slow)) == ("TIMEOUT", None)
    broken = result("", status="internal", exit_code=None)
    assert compare.verdict(broken, expected, compare.observe(broken)) == ("ERROR", None)


# --- классификация эталона ----------------------------------------------------------------------------


def test_equal_runs_are_stable_and_baseline_takes_the_faster_time():
    out = compare.classify(result("x\n", duration_ms=40), result("x\n", duration_ms=25))
    assert out.stability == "stable"
    assert out.baseline.stdout == "x"
    assert out.baseline.duration_ms == 25
    assert out.masks == [] and out.warnings == []


def test_runs_that_differ_in_numbers_become_masked_automatically():
    out = compare.classify(result("took 12 ms\nok\n"), result("took 97 ms\nok\n"))
    assert out.stability == "masked"
    assert out.masks
    assert out.baseline.stdout == "took <TIME>\nok"
    assert out.warnings


def test_user_masks_make_a_scenario_masked():
    masks = [Mask(r"\d+", "<N>")]
    out = compare.classify(result("n=1"), result("n=2"), masks)
    assert out.stability == "masked"
    assert out.masks == masks


def test_runs_that_cannot_be_masked_are_nondeterministic():
    out = compare.classify(result("alpha\n"), result("beta\n"))
    assert out.stability == "nondeterministic"
    assert any("исключён" in w for w in out.warnings)


def test_different_exit_code_is_nondeterministic():
    out = compare.classify(result("x", exit_code=0), result("x", exit_code=1))
    assert out.stability == "nondeterministic"


def test_timeout_during_baseline_is_not_recorded():
    out = compare.classify(result("x"), result("", status="timeout", exit_code=None))
    assert out.stability == "nondeterministic"
    assert any("время" in w for w in out.warnings)
