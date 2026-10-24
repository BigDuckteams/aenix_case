"""Расширенные правила (S7.6): PERF-04, PERF-08, BUG-07, BUG-09, BUG-10, MAINT-06, 07, 10 — срабатывание и «чистый» пример."""

from __future__ import annotations

from engine.analysis.analyzer import analyze
from engine.java.project import JavaProject


def source(body: str, members: str = "", name: str = "A") -> JavaProject:
    text = (
        "import java.util.*;\n"
        f"class {name} {{\n{members}\n    void run(List<String> items, int n) {{\n{body}\n    }}\n}}\n"
    )
    return JavaProject({f"{name}.java": text})


def rules(project: JavaProject) -> dict[str, list]:
    found: dict[str, list] = {}
    for finding in analyze(project).findings:
        found.setdefault(finding.rule_id, []).append(finding)
    return found


# --- PERF-04 -------------------------------------------------------------------------------------------------


def test_perf_04_sort_inside_a_loop():
    for call in ("Collections.sort(items);", "items.sort(null);"):
        [finding] = rules(source(f"        for (int i = 0; i < n; i++) {{ {call} }}"))["PERF-04"]
        assert finding.severity == "medium"
        assert (
            finding.complexity.current == "O(n² log n)" and finding.complexity.after == "O(n log n)"
        )


def test_perf_04_ignores_sorting_outside_loops_and_loop_local_collections():
    clean = [
        "Collections.sort(items); for (int i = 0; i < n; i++) { n--; }",
        "for (int i = 0; i < n; i++) { List<String> local = new ArrayList<>(); Collections.sort(local); }",
        "for (int i = 0; i < 3; i++) { Collections.sort(items); }",
    ]
    for body in clean:
        assert "PERF-04" not in rules(source(body)), body


# --- PERF-08 -------------------------------------------------------------------------------------------------


def test_perf_08_recursion_without_memoisation():
    fib = "    int fib(int k) {\n        if (k < 2) return k;\n        return fib(k - 1) + fib(k - 2);\n    }"
    [finding] = rules(source("n++;", fib))["PERF-08"]
    assert finding.complexity.current == "O(2ⁿ)" and finding.complexity.after == "O(n)"
    assert "fib" in finding.title


def test_perf_08_ignores_linear_recursion_and_memoised_versions():
    linear = "    int f(int k) {\n        if (k < 2) return 1;\n        return k * f(k - 1);\n    }"
    memo = (
        "    Map<Integer, Integer> memo = new HashMap<>();\n"
        "    int fib(int k) {\n        if (k < 2) return k;\n"
        "        return memo.computeIfAbsent(k, x -> fib(x - 1) + fib(x - 2));\n    }"
    )
    assert "PERF-08" not in rules(source("n++;", linear))
    assert "PERF-08" not in rules(source("n++;", memo))


# --- BUG-07 / BUG-09 / BUG-10 ------------------------------------------------------------------------------------


def test_bug_07_discarded_string_result():
    [finding] = rules(
        source("        String s = items.get(0);\n        s.trim();\n        s.toUpperCase();")
    )["BUG-07"][:1]
    assert finding.severity == "high" and "trim" in finding.title
    assert (
        len(
            rules(
                source(
                    "        String s = items.get(0);\n        s.trim();\n        s.toUpperCase();"
                )
            )["BUG-07"]
        )
        == 2
    )


def test_bug_07_ignores_used_results():
    clean = "        String s = items.get(0);\n        s = s.trim();\n        System.out.println(s.toUpperCase());\n        items.add(s.trim());"
    assert "BUG-07" not in rules(source(clean))


def test_bug_09_modifying_the_iterated_collection():
    body = "        for (String s : items) {\n            if (s.isEmpty()) {\n                items.remove(s);\n            }\n        }"
    [finding] = rules(source(body))["BUG-09"]
    assert finding.severity == "high" and "ConcurrentModificationException" in finding.explanation
    clean = [
        "        for (String s : items) {\n            if (s.isEmpty()) {\n                items.remove(s);\n                break;\n            }\n        }",
        "        List<String> copy = new ArrayList<>(items);\n        for (String s : copy) {\n            items.remove(s);\n        }",
        "        items.removeIf(String::isEmpty);",
    ]
    for body in clean:
        assert "BUG-09" not in rules(source(body)), body


def test_bug_10_switch_without_default_and_fall_through():
    no_default = "        switch (n) {\n            case 1:\n                n++;\n                break;\n            case 2:\n                n--;\n                break;\n        }"
    [finding] = rules(source(no_default))["BUG-10"]
    assert finding.severity == "low" and "default" in finding.explanation
    fall = "        switch (n) {\n            case 1:\n                n++;\n            case 2:\n                n--;\n                break;\n            default:\n                break;\n        }"
    [fall_finding] = rules(source(fall))["BUG-10"]
    assert fall_finding.severity == "medium" and "проваливается" in fall_finding.explanation
    clean = "        switch (n) {\n            case 1:\n            case 2:\n                n++;\n                break;\n            default:\n                break;\n        }"
    assert "BUG-10" not in rules(source(clean))


# --- MAINT --------------------------------------------------------------------------------------------------------


def test_maint_06_repeated_magic_numbers_and_strings():
    body = "        if (n > 42) { n = 42; }\n        n += 7;"
    [finding] = rules(source(body))["MAINT-06"]
    assert "42" in finding.title and finding.severity == "low"
    strings = '        System.out.println("значение: " + n);\n        System.out.println("значение: " + n);\n        System.out.println("значение: " + n);'
    assert any("значение" in f.title for f in rules(source(strings))["MAINT-06"])


def test_maint_06_ignores_trivial_and_single_use_values():
    clean = "        n = n * 2 + 3;\n        n += 0;\n        n -= 1;\n        n = n > 0 ? 1 : 0;"
    assert "MAINT-06" not in rules(source(clean))
    in_case = "        switch (n) { case 42: n++; break; case 43: n--; break; default: break; }\n        n += 99;"
    assert "MAINT-06" not in rules(source(in_case))


def test_maint_07_unused_private_members_and_locals():
    members = "    private int helper() { return 1; }\n    private int stale = 5;\n    private int used = 1;\n    int read() { return used; }"
    project = source(
        "        int unusedLocal = 3;\n        int kept = 4;\n        n += kept;", members
    )
    titles = sorted(f.title for f in rules(project)["MAINT-07"])
    assert titles == [
        "Неиспользуемая переменная unusedLocal",
        "Неиспользуемое приватное поле stale",
        "Неиспользуемый приватный метод helper",
    ]


def test_maint_07_ignores_used_privates():
    members = "    private int helper() { return 1; }\n    private int used = 1;"
    project = source("        n += helper() + used;", members)
    assert "MAINT-07" not in rules(project)


def test_maint_10_naming_conventions():
    members = "    void Do_Thing() { }\n    int Total;\n    static final int limit = 3;\n    static final int OK_VALUE = 1;\n    private static final long serialVersionUID = 1L;"
    project = source("n++;", members, name="badName")
    titles = {f.title for f in rules(project)["MAINT-10"]}
    assert titles == {
        "Имя не по соглашению: badName",
        "Имя не по соглашению: Do_Thing",
        "Имя не по соглашению: Total",
        "Имя не по соглашению: limit",
    }


def test_new_rules_keep_demo_orders_deterministic_and_fast():
    import time
    from pathlib import Path

    root = Path(__file__).resolve().parents[3] / "samples" / "demo-orders"
    project = JavaProject(
        {
            p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
            for p in root.rglob("*.java")
        }
    )
    started = time.perf_counter()
    first = analyze(project)
    assert time.perf_counter() - started < 1.0
    again = analyze(JavaProject(project.files))
    assert [f.id for f in first.findings] == [f.id for f in again.findings]
    assert {"MAINT-06"} <= {f.rule_id for f in first.findings}
