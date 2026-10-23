"""Проверка корпуса примеров `samples/` (инварианты I4 и I5, docs/10-quality-and-testing.md § 3.2).

    python scripts/verify_corpus.py                      # весь корпус
    python scripts/verify_corpus.py demo-orders scope    # только примеры, в пути которых есть эти слова
    python scripts/verify_corpus.py --update-golden      # записать expected_stdout в сценарии

Для каждого примера: поиск запрещённых конструкций (вне `out-of-scope/`), `javac`, затем каждый
сценарий запускается дважды, и нормализованный вывод должен совпасть (определённость), а также
код выхода и, если задан, `expected_stdout`. Файлы `samples/broken/*.java` обязаны НЕ компилироваться.

Только стандартная библиотека Python: скрипт работает без `uv sync`. Нужен JDK (`javac`, `java`):
PATH, `--java-home`, `JB_JAVA_HOME` или `JAVA_HOME`. Если JDK старше 21, берётся его собственный
`--release` с предупреждением (CI использует JDK 21).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = REPO_ROOT / "samples"
TARGET_RELEASE = 21

# Минимальное число сценариев на пример: «каталог верхнего уровня или имя» → число (docs/10 § 2).
MIN_SCENARIOS = {"demo-orders": 8, "scope": 2, "default": 3}

# Конструкции вне рамок кейса (docs/04 § 9.3) и источники недетерминизма.
FORBIDDEN = {
    "потоки и java.util.concurrent": r"\bThread\b|\bRunnable\b|\bExecutor\w*\b|java\.util\.concurrent"
    r"|\bsynchronized\b|\bvolatile\b|\bCompletableFuture\b",
    "java.time": r"java\.time|\bLocalDate\w*\b|\bInstant\b|\bZonedDateTime\b",
    "файлы и java.nio": r"java\.nio\.file|java\.io\.File\b|\bFileReader\b|\bFileWriter\b"
    r"|\bFileInputStream\b|\bFileOutputStream\b|\bFiles\.|\bPaths?\.(?:get|of)\b|\bnew File\(",
    "сеть": r"java\.net|\bSocket\b|\bHttpClient\b|\bnew URL\(",
    "рефлексия": r"java\.lang\.reflect|Class\.forName|\.getDeclared\w+\(",
    "недетерминизм": r"System\.currentTimeMillis|System\.nanoTime|Math\.random\(\)"
    r"|new Random\(\s*\)|new Date\(|UUID\.randomUUID",
}

JVM_FLAGS = [
    "-Dfile.encoding=UTF-8",
    "-Dstdout.encoding=UTF-8",
    "-Dstderr.encoding=UTF-8",
    "-Dsun.stdout.encoding=UTF-8",
    "-Duser.language=en",
    "-Duser.country=US",
    "-Duser.timezone=UTC",
    "-Xmx256m",
    "-Xss1m",
    "-XX:+UseSerialGC",
    "-XX:TieredStopAtLevel=1",
    "-Xshare:auto",
]


@dataclass
class Jdk:
    javac: str
    java: str
    major: int
    version: str

    @property
    def release(self) -> int:
        return min(self.major, TARGET_RELEASE)


@dataclass
class Result:
    name: str
    ok: bool = True
    problems: list[str] = field(default_factory=list)
    scenarios: int = 0
    runs: int = 0
    warnings: int = 0
    seconds: float = 0.0

    def fail(self, message: str) -> None:
        self.ok = False
        self.problems.append(message)


# --- JDK ---------------------------------------------------------------------------------------


def find_jdk(java_home: str | None) -> Jdk:
    home = java_home or os.environ.get("JB_JAVA_HOME") or os.environ.get("JAVA_HOME")
    search = str(Path(home) / "bin") if home else None
    javac = shutil.which("javac", path=search) or shutil.which("javac")
    java = shutil.which("java", path=search) or shutil.which("java")
    if not javac or not java:
        raise SystemExit("javac/java не найдены: задайте --java-home, JB_JAVA_HOME или PATH")
    out = subprocess.run([javac, "-version"], capture_output=True, text=True, encoding="utf-8")
    match = re.search(r"javac\s+(\d+)(?:\.\d+)*", out.stdout + out.stderr)
    if not match:
        raise SystemExit(f"не удалось определить версию javac: {out.stdout}{out.stderr}")
    version = match.group(0).split()[1]
    return Jdk(javac, java, int(match.group(1)), version)


# --- Обнаружение примеров ----------------------------------------------------------------------


def discover(root: Path) -> list[Path]:
    """Пример — каталог, в котором есть подкаталог `scenarios/` (кроме `broken/`)."""
    found = []
    for scenarios in sorted(root.rglob("scenarios")):
        if scenarios.is_dir() and "broken" not in scenarios.relative_to(root).parts:
            found.append(scenarios.parent)
    return found


def java_files(sample: Path) -> list[Path]:
    return sorted(p for p in sample.rglob("*.java") if "scenarios" not in p.relative_to(sample).parts)


def strip_java(source: str) -> str:
    """Убирает строки и комментарии, чтобы поиск запрещённых слов не срабатывал на текст."""
    source = re.sub(r'"""[\s\S]*?"""', '""', source)
    source = re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', source)
    source = re.sub(r"'(?:[^'\\\n]|\\.)+'", "' '", source)
    source = re.sub(r"/\*[\s\S]*?\*/", " ", source)
    return re.sub(r"//[^\n]*", "", source)


def main_class(sample: Path, files: list[Path]) -> str | None:
    config = sample / "sample.json"
    if config.exists():
        configured = json.loads(config.read_text(encoding="utf-8")).get("main_class")
        if configured:
            return str(configured)
    candidates = []
    for path in files:
        text = strip_java(path.read_text(encoding="utf-8"))
        if re.search(r"public\s+static\s+void\s+main\s*\(", text):
            package = re.search(r"^\s*package\s+([\w.]+)\s*;", text, re.M)
            candidates.append((package.group(1) + "." if package else "") + path.stem)
    if len(candidates) == 1:
        return candidates[0]
    for candidate in candidates:
        if candidate.rsplit(".", 1)[-1] == "Main":
            return candidate
    return None


# --- Запуск Java -------------------------------------------------------------------------------


def normalize_stdout(text: str) -> str:
    return text.replace("\r\n", "\n").rstrip("\n")


def normalize_stderr(text: str) -> str:
    """Из стека остаются тип и сообщение исключения (docs/07 § 3.2)."""
    lines = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if line.startswith(("\tat ", "\t... ", "Picked up ")) or not line.strip():
            continue
        lines.append(line)
    return "\n".join(lines)


def compile_sample(jdk: Jdk, files: list[Path], out_dir: Path, work: Path) -> tuple[bool, str]:
    sources = work / "sources.txt"
    sources.write_text(
        "\n".join(f'"{p.as_posix()}"' for p in files) + "\n",
        encoding="utf-8",
    )
    command = [
        jdk.javac,
        "--release",
        str(jdk.release),
        "-encoding",
        "UTF-8",
        "-g",
        "-Xlint:all",
        "-d",
        str(out_dir),
        f"@{sources}",
    ]
    proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=120)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def run_java(jdk: Jdk, classes: Path, main: str, scenario: dict, cwd: Path, timeout: float) -> dict:
    command = [jdk.java, *JVM_FLAGS, "-cp", str(classes), main, *scenario.get("args", [])]
    env = {**os.environ, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    env.pop("JAVA_TOOL_OPTIONS", None)
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            input=scenario.get("stdin", "").encode("utf-8"),
            capture_output=True,
            cwd=cwd,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"timeout": True, "seconds": time.monotonic() - started}
    return {
        "timeout": False,
        "exit": proc.returncode,
        "stdout": normalize_stdout(proc.stdout.decode("utf-8", errors="replace")),
        "stderr": normalize_stderr(proc.stderr.decode("utf-8", errors="replace")),
        "seconds": time.monotonic() - started,
    }


def load_scenarios(sample: Path, result: Result) -> list[tuple[Path, dict]]:
    scenarios = []
    for path in sorted((sample / "scenarios").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            result.fail(f"{path.name}: неверный JSON ({exc})")
            continue
        if not isinstance(data, dict) or not data.get("name") or "stdin" not in data:
            result.fail(f"{path.name}: нужны поля name и stdin")
            continue
        if data["name"] != path.stem:
            result.fail(f"{path.name}: name «{data['name']}» должно совпадать с именем файла")
        scenarios.append((path, data))
    return scenarios


def min_scenarios(sample: Path, root: Path) -> int:
    parts = sample.relative_to(root).parts
    return MIN_SCENARIOS.get(parts[-1]) or MIN_SCENARIOS.get(parts[0]) or MIN_SCENARIOS["default"]


# --- Проверка одного примера -------------------------------------------------------------------


def check_sample(
    sample: Path, root: Path, jdk: Jdk, update_golden: bool, timeout: float
) -> Result:
    name = sample.relative_to(root).as_posix()
    result = Result(name)
    started = time.monotonic()
    files = java_files(sample)
    if not files:
        result.fail("нет .java файлов")
        return result

    if "out-of-scope" not in sample.relative_to(root).parts:
        for path in files:
            code = strip_java(path.read_text(encoding="utf-8"))
            for title, pattern in FORBIDDEN.items():
                hit = re.search(pattern, code)
                if hit:
                    line = code[: hit.start()].count("\n") + 1
                    result.fail(f"{path.name}:{line}: вне рамок ({title}): «{hit.group(0)}»")

    scenarios = load_scenarios(sample, result)
    needed = min_scenarios(sample, root)
    if len(scenarios) < needed:
        result.fail(f"сценариев {len(scenarios)}, нужно не меньше {needed}")
    result.scenarios = len(scenarios)

    main = main_class(sample, files)
    if main is None:
        result.fail("не найден единственный main-класс (задайте main_class в sample.json)")
        return result

    with tempfile.TemporaryDirectory(prefix="jb-corpus-") as tmp:
        work = Path(tmp)
        classes = work / "classes"
        classes.mkdir()
        ok, log = compile_sample(jdk, files, classes, work)
        result.warnings = len(re.findall(r": warning:", log))
        if not ok:
            first = "\n".join(log.splitlines()[:6])
            result.fail(f"javac не прошёл:\n{first}")
            return result

        run_dir = work / "run"
        run_dir.mkdir()
        for path, scenario in scenarios:
            first = run_java(jdk, classes, main, scenario, run_dir, timeout)
            second = run_java(jdk, classes, main, scenario, run_dir, timeout)
            result.runs += 2
            label = f"{scenario['name']}"
            if first["timeout"] or second["timeout"]:
                result.fail(f"{label}: превышено время {timeout:.0f} с")
                continue
            for key in ("exit", "stdout", "stderr"):
                if first[key] != second[key]:
                    result.fail(f"{label}: недетерминирован ({key} различается между прогонами)")
                    break
            else:
                check_expectations(result, path, scenario, first, update_golden)
    result.seconds = time.monotonic() - started
    return result


def check_expectations(
    result: Result, path: Path, scenario: dict, run: dict, update_golden: bool
) -> None:
    label = scenario["name"]
    expected_exit = scenario.get("expected_exit_code", 0)
    if run["exit"] != expected_exit:
        tail = run["stderr"].splitlines()[:2]
        result.fail(f"{label}: код выхода {run['exit']}, ожидался {expected_exit} {tail}")
        return
    if update_golden:
        scenario["expected_stdout"] = run["stdout"]
        text = json.dumps(scenario, ensure_ascii=False, indent=2) + "\n"
        path.write_text(text, encoding="utf-8", newline="\n")
        return
    if "expected_stdout" in scenario and normalize_stdout(scenario["expected_stdout"]) != run["stdout"]:
        actual = run["stdout"].splitlines()
        expected = normalize_stdout(scenario["expected_stdout"]).splitlines()
        for number, (a, e) in enumerate(zip(actual, expected, strict=False), 1):
            if a != e:
                result.fail(f"{label}: вывод отличается от expected_stdout, строка {number}: «{a}» вместо «{e}»")
                return
        result.fail(f"{label}: вывод отличается от expected_stdout (длина {len(actual)} и {len(expected)} строк)")


def check_broken(root: Path, jdk: Jdk) -> list[Result]:
    """Файлы из `broken/` обязаны не компилироваться: иначе они не проверяют устойчивость разбора."""
    results = []
    for path in sorted((root / "broken").glob("*.java")) if (root / "broken").is_dir() else []:
        result = Result(f"broken/{path.name}")
        with tempfile.TemporaryDirectory(prefix="jb-broken-") as tmp:
            work = Path(tmp)
            (work / "classes").mkdir()
            ok, _ = compile_sample(jdk, [path], work / "classes", work)
        if ok:
            result.fail("файл компилируется, а должен содержать ошибку")
        results.append(result)
    return results


# --- main --------------------------------------------------------------------------------------


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Проверка корпуса samples/")
    parser.add_argument("filters", nargs="*", help="проверять только примеры с такой подстрокой в пути")
    parser.add_argument("--samples", type=Path, default=SAMPLES_DIR)
    parser.add_argument("--java-home")
    parser.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 2))
    parser.add_argument("--timeout", type=float, default=30.0, help="секунд на один запуск")
    parser.add_argument("--update-golden", action="store_true", help="записать expected_stdout")
    parser.add_argument("--json", type=Path, help="сохранить отчёт в JSON")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    jdk = find_jdk(args.java_home)
    print(f"JDK: javac {jdk.version}, --release {jdk.release}")
    if jdk.major < TARGET_RELEASE:
        print(f"ПРЕДУПРЕЖДЕНИЕ: JDK старше {TARGET_RELEASE}; конструкции Java {TARGET_RELEASE} не проверены")

    root = args.samples.resolve()
    samples = [
        s for s in discover(root) if not args.filters or any(f in s.as_posix() for f in args.filters)
    ]
    if not samples:
        print("Примеры не найдены")
        return 1

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = [
            pool.submit(check_sample, s, root, jdk, args.update_golden, args.timeout) for s in samples
        ]
        results = [f.result() for f in futures]
    if not args.filters:
        results += check_broken(root, jdk)

    for r in results:
        status = "[ OK ]" if r.ok else "[FAIL]"
        extra = f"сценариев {r.scenarios}, запусков {r.runs}" if r.scenarios else ""
        print(f"{status} {r.name:<36} {extra}")
        for problem in r.problems:
            print("       - " + problem.replace("\n", "\n         "))
    failed = [r for r in results if not r.ok]
    total_runs = sum(r.runs for r in results)
    print(
        f"\nПримеров: {len(results)}, прогонов JVM: {total_runs}, "
        f"ошибок: {len(failed)}, {time.monotonic() - started:.1f} с"
    )
    if args.json:
        report = [
            {"name": r.name, "ok": r.ok, "problems": r.problems, "scenarios": r.scenarios}
            for r in results
        ]
        text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        args.json.write_text(text, encoding="utf-8", newline="\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
