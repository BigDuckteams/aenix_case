"""`scripts/verify_corpus.py`: поиск запрещённых конструкций, нормализация и проверка на синтетических примерах."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "verify_corpus.py"
spec = importlib.util.spec_from_file_location("verify_corpus", SCRIPT)
assert spec and spec.loader
verify_corpus = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = verify_corpus  # dataclass ищет свой модуль в sys.modules
spec.loader.exec_module(verify_corpus)


def forbidden(source: str) -> list[str]:
    code = verify_corpus.strip_java(source)
    return [title for title, pattern in verify_corpus.FORBIDDEN.items() if re.search(pattern, code)]


def test_strip_java_removes_strings_and_comments():
    source = 'String s = "Thread // not a comment"; // Thread\n/* java.time */ int x = 1; char c = \'"\';'
    stripped = verify_corpus.strip_java(source)
    assert "Thread" not in stripped
    assert "java.time" not in stripped
    assert "int x = 1;" in stripped


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Thread t = new Thread(() -> {});", "потоки"),
        ("synchronized void f() {}", "потоки"),
        ("import java.time.LocalDate;", "java.time"),
        ("Files.readAllLines(path);", "файлы"),
        ("new FileReader(name)", "файлы"),
        ("Class.forName(name)", "рефлексия"),
        ("long t = System.nanoTime();", "недетерминизм"),
        ("new Random()", "недетерминизм"),
        ("Math.random()", "недетерминизм"),
    ],
)
def test_forbidden_constructs_are_detected(source, expected):
    assert any(expected in title for title in forbidden(source)), forbidden(source)


@pytest.mark.parametrize(
    "source",
    [
        'System.out.println("Thread");',
        "new Random(42).nextInt(10);",
        "BufferedReader r = new BufferedReader(new InputStreamReader(System.in));",
        "// java.time.LocalDate is mentioned in a comment",
        "Runtime.getRuntime();",
        "e.getClass().getSimpleName();",
    ],
)
def test_allowed_code_is_not_flagged(source):
    assert forbidden(source) == []


def test_normalize_stdout_and_stderr():
    assert verify_corpus.normalize_stdout("a\r\nb\r\n\r\n") == "a\nb"
    stderr = (
        'Picked up JAVA_TOOL_OPTIONS: -Xmx1g\nException in thread "main" X: msg\n'
        "\tat Main.main(Main.java:5)\n\n"
    )
    assert verify_corpus.normalize_stderr(stderr) == 'Exception in thread "main" X: msg'


def test_main_class_detection(tmp_path):
    (tmp_path / "Helper.java").write_text("class Helper {}", encoding="utf-8")
    (tmp_path / "App.java").write_text(
        "public class App { public static void main(String[] a) {} }", encoding="utf-8"
    )
    files = verify_corpus.java_files(tmp_path)
    assert verify_corpus.main_class(tmp_path, files) == "App"

    pkg = tmp_path / "com" / "x"
    pkg.mkdir(parents=True)
    (pkg / "Main.java").write_text(
        "package com.x;\npublic class Main { public static void main(String[] a) {} }",
        encoding="utf-8",
    )
    files = verify_corpus.java_files(tmp_path)
    assert verify_corpus.main_class(tmp_path, files) == "com.x.Main"  # Main предпочтительнее

    (tmp_path / "sample.json").write_text('{"main_class": "App"}', encoding="utf-8")
    assert verify_corpus.main_class(tmp_path, files) == "App"


def test_discover_skips_broken_and_non_samples(tmp_path):
    (tmp_path / "a" / "scenarios").mkdir(parents=True)
    (tmp_path / "scope" / "01-x" / "scenarios").mkdir(parents=True)
    (tmp_path / "broken" / "scenarios").mkdir(parents=True)
    (tmp_path / "plain").mkdir()
    found = [p.relative_to(tmp_path).as_posix() for p in verify_corpus.discover(tmp_path)]
    assert found == ["a", "scope/01-x"]


# --- Синтетические примеры с настоящим JDK (джоб CI `backend-jdk`) ------------------------------

GOOD = """
import java.util.Scanner;
public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int n = in.nextInt();
        System.out.println("привет " + (n * 2));
        if (n < 0) {
            throw new IllegalStateException("отрицательное");
        }
    }
}
"""


def make_sample(root: Path, name: str, source: str, scenarios: list[dict]) -> Path:
    sample = root / name
    (sample / "scenarios").mkdir(parents=True)
    (sample / "Main.java").write_text(source, encoding="utf-8")
    for scenario in scenarios:
        path = sample / "scenarios" / f"{scenario['name']}.json"
        path.write_text(json.dumps(scenario, ensure_ascii=False), encoding="utf-8")
    return sample


def scenario(name: str, stdin: str = "1\n", **extra) -> dict:
    return {"name": name, "description": name, "stdin": stdin, "args": [], **extra}


def run_script(root: Path, *extra: str) -> int:
    return verify_corpus.run(["--samples", str(root), "--jobs", "1", *extra])


@pytest.mark.jdk
def test_good_sample_passes_and_golden_roundtrip(tmp_path, capsys):
    make_sample(
        tmp_path,
        "good",
        GOOD,
        [
            scenario("a", "2\n"),
            scenario("b", "5\n"),
            scenario("crash", "-1\n", expected_exit_code=1),
        ],
    )
    assert run_script(tmp_path, "--update-golden") == 0
    golden = json.loads((tmp_path / "good" / "scenarios" / "a.json").read_text(encoding="utf-8"))
    assert golden["expected_stdout"] == "привет 4"
    assert run_script(tmp_path) == 0
    assert "[ OK ] good" in capsys.readouterr().out


@pytest.mark.jdk
def test_changed_output_fails_golden(tmp_path, capsys):
    make_sample(
        tmp_path, "g", GOOD, [scenario(n, "3\n", expected_stdout="привет 7") for n in "abc"]
    )
    assert run_script(tmp_path) == 1
    assert "expected_stdout" in capsys.readouterr().out


@pytest.mark.jdk
def test_wrong_exit_code_fails(tmp_path, capsys):
    make_sample(tmp_path, "x", GOOD, [scenario(n, "-5\n") for n in "abc"])
    assert run_script(tmp_path) == 1
    assert "код выхода 1" in capsys.readouterr().out


@pytest.mark.jdk
def test_nondeterministic_output_is_detected(tmp_path, capsys):
    source = GOOD.replace('"привет " + (n * 2)', '"pid " + ProcessHandle.current().pid()')
    make_sample(tmp_path, "pid", source, [scenario(n) for n in "abc"])
    assert run_script(tmp_path) == 1
    assert "недетерминирован" in capsys.readouterr().out


@pytest.mark.jdk
def test_compile_error_and_missing_scenarios_fail(tmp_path, capsys):
    make_sample(tmp_path, "bad", GOOD.replace("int n =", "int n = ;"), [scenario(n) for n in "abc"])
    make_sample(tmp_path, "few", GOOD, [scenario("only")])
    assert run_script(tmp_path) == 1
    out = capsys.readouterr().out
    assert "javac не прошёл" in out
    assert "сценариев 1, нужно не меньше 3" in out


@pytest.mark.jdk
def test_forbidden_construct_fails_outside_out_of_scope(tmp_path, capsys):
    threaded = GOOD.replace("int n =", "Thread t = new Thread(); int n =")
    make_sample(tmp_path, "threads", threaded, [scenario(n) for n in "abc"])
    make_sample(tmp_path / "out-of-scope", "threads", threaded, [scenario(n) for n in "abc"])
    assert run_script(tmp_path) == 1
    out = capsys.readouterr().out
    assert "[FAIL] threads" in out
    assert "[ OK ] out-of-scope/threads" in out


@pytest.mark.jdk
def test_broken_files_must_fail_to_compile(tmp_path, capsys):
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "Bad.java").write_text("class Bad { void f( }", encoding="utf-8")
    (broken / "Fine.java").write_text("class Fine { }", encoding="utf-8")
    make_sample(tmp_path, "ok", GOOD, [scenario(n) for n in "abc"])
    assert run_script(tmp_path) == 1
    out = capsys.readouterr().out
    assert "[ OK ] broken/Bad.java" in out
    assert "[FAIL] broken/Fine.java" in out
