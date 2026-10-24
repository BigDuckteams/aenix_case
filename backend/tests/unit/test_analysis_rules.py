"""Правила диагностики и метрики (S7.3–S7.5): у каждого правила срабатывание и «чистый» пример."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from engine.analysis.analyzer import analyze, estimate_node, estimate_range
from engine.java.project import JavaProject

SAMPLES = Path(__file__).resolve().parents[3] / "samples"


def project_of(body: str, members: str = "", name: str = "A") -> JavaProject:
    source = (
        "import java.util.*;\nimport java.util.stream.*;\n"
        f"class {name} {{\n{members}\n    void run(List<String> items, int n) {{\n{body}\n    }}\n}}\n"
    )
    return JavaProject({f"{name}.java": source})


def rules_of(project: JavaProject, **thresholds: float) -> dict[str, list]:
    found: dict[str, list] = {}
    for finding in analyze(project, thresholds).findings:
        found.setdefault(finding.rule_id, []).append(finding)
    return found


# --- PERF-01 -------------------------------------------------------------------------------------------


SLIDE_5 = """
        for (String a : items) {
            for (String b : items) {
                if (a.equals(b)) {
                    n++;
                }
            }
        }"""


def test_perf_01_matches_the_slide_5_example_with_full_explanation():
    project = project_of(SLIDE_5)
    [finding] = rules_of(project)["PERF-01"]
    assert finding.severity == "high" and finding.category == "PERF"
    assert finding.id == "PERF-01:A.java#A.run(List<String>, int)/foreach[0]"
    assert finding.location.node_id == "A.java#A.run(List<String>, int)/foreach[0]"
    assert (finding.location.start_line, finding.location.end_line) == (7, 13)
    assert finding.title == "Вложенный цикл — O(n²)"
    assert "n²" in finding.explanation and "a.equals(b)" in finding.explanation
    assert finding.defect and finding.risk and "Map" in finding.recommendation
    assert finding.complexity.current == "O(n²)" and finding.complexity.after == "O(n)"
    assert finding.complexity.confidence == "exact"
    assert [c.factor for c in finding.complexity.contributions] == ["n", "n"]
    assert {e.kind for e in finding.evidence.static} == {"loop", "condition"}


def test_perf_01_works_with_indexed_loops_and_key_equality():
    body = """
        for (int i = 0; i < n; i++) {
            for (int j = i + 1; j < n; j++) {
                if (items.get(i).equals(items.get(j))) {
                    n--;
                }
            }
        }"""
    assert "PERF-01" in rules_of(project_of(body))


def test_perf_01_is_not_reported_without_key_comparison_or_for_constant_loops():
    no_compare = """
        for (String a : items) {
            for (String b : items) {
                if (a.length() > b.length()) {
                    n++;
                }
            }
        }"""
    constant = """
        for (int i = 0; i < 3; i++) {
            for (int j = 0; j < 3; j++) {
                if (items.get(i).equals(items.get(j))) {
                    n++;
                }
            }
        }"""
    only_inner = """
        for (String a : items) {
            if (a.equals("x")) {
                n++;
            }
        }"""
    for body in (no_compare, constant, only_inner):
        assert "PERF-01" not in rules_of(project_of(body))


# --- PERF-02 / PERF-03 / PERF-06 ----------------------------------------------------------------------------


def test_perf_02_flags_contains_on_a_list_inside_a_loop():
    body = """
        List<String> seen = new ArrayList<>();
        for (String s : items) {
            if (!seen.contains(s)) {
                seen.add(s);
            }
        }"""
    [finding] = rules_of(project_of(body))["PERF-02"]
    assert finding.severity == "high"
    assert "contains" in finding.title
    assert finding.complexity.current == "O(n²)" and finding.complexity.after == "O(n)"
    assert (finding.location.start_line, finding.location.end_line) == (9, 9)
    assert "HashSet" in finding.recommendation


def test_perf_02_ignores_sets_outside_loops_and_constant_loops():
    clean = [
        "Set<String> seen = new HashSet<>(); for (String s : items) { if (!seen.contains(s)) { seen.add(s); } }",
        'if (items.contains("x")) { n++; }',
        'for (int i = 0; i < 3; i++) { if (items.contains("x")) { n++; } }',
        "for (String s : items) { List<String> local = new ArrayList<>(); if (local.contains(s)) { n++; } }",
        'String text = "abc"; for (String s : items) { if (text.contains(s)) { n++; } }',
    ]
    for body in clean:
        assert "PERF-02" not in rules_of(project_of(body)), body


def test_perf_02_remove_by_index_is_not_a_linear_search():
    body = "for (int i = 0; i < n; i++) { items.remove(0); }"
    assert "PERF-02" not in rules_of(project_of(body))
    assert "PERF-02" in rules_of(project_of('for (int i = 0; i < n; i++) { items.remove("x"); }'))


def test_perf_03_flags_string_concatenation_in_a_loop():
    for update in ("result += s;", 'result = result + s + ",";'):
        body = f'String result = ""; for (String s : items) {{ {update} }}'
        [finding] = rules_of(project_of(body))["PERF-03"]
        assert finding.severity == "medium"
        assert finding.complexity.current == "O(n²)" and finding.complexity.after == "O(n)"
        assert "StringBuilder" in finding.recommendation


def test_perf_03_ignores_builders_constant_loops_and_loop_local_strings():
    clean = [
        "StringBuilder sb = new StringBuilder(); for (String s : items) { sb.append(s); }",
        'String r = ""; for (int i = 0; i < 3; i++) { r += i; }',
        'for (String s : items) { String line = ""; line += s; n += line.length(); }',
        'String r = ""; r += "x";',
    ]
    for body in clean:
        assert "PERF-03" not in rules_of(project_of(body)), body


def test_perf_06_flags_linked_list_indexing_and_front_inserts():
    linked = "LinkedList<String> l = new LinkedList<>(items); for (int i = 0; i < l.size(); i++) { n += l.get(i).length(); }"
    front = "ArrayList<String> a = new ArrayList<>(); for (String s : items) { a.add(0, s); }"
    for body in (linked, front):
        [finding] = rules_of(project_of(body))["PERF-06"]
        assert finding.severity == "medium"
        assert finding.complexity.current == "O(n²)"
    clean = "ArrayList<String> a = new ArrayList<>(items); for (int i = 0; i < a.size(); i++) { n += a.get(i).length(); a.add(s(i)); }"
    assert "PERF-06" not in rules_of(project_of(clean, 'String s(int i) { return ""; }'))


# --- BUG ---------------------------------------------------------------------------------------------------------


def test_bug_01_flags_string_reference_comparison():
    for expression in ('items.get(0) == "a"', "items.get(0) != items.get(1)", '"a" == "b"'):
        body = f"if ({expression}) {{ n++; }}"
        [finding] = rules_of(project_of(body))["BUG-01"]
        assert finding.severity == "high" and finding.category == "BUG"
        assert "equals" in finding.recommendation


def test_bug_01_ignores_equals_null_checks_and_numbers():
    clean = [
        'if ("a".equals(items.get(0))) { n++; }',
        "if (items.get(0) == null) { n++; }",
        "if (n == 3) { n++; }",
        "String s = null; if (s != null) { n++; }",
    ]
    for body in clean:
        assert "BUG-01" not in rules_of(project_of(body)), body


def test_bug_02_flags_empty_catch_blocks_only():
    empty = "try { n = Integer.parseInt(items.get(0)); } catch (NumberFormatException e) { }"
    only_comment = "try { n = 1; } catch (Exception e) { /* ignore */ }"
    handled = "try { n = 1; } catch (Exception e) { System.err.println(e); }"
    assert len(rules_of(project_of(empty))["BUG-02"]) == 1
    assert len(rules_of(project_of(only_comment))["BUG-02"]) == 1
    assert "BUG-02" not in rules_of(project_of(handled))


# --- MAINT ---------------------------------------------------------------------------------------------------------


def test_maint_01_and_09_follow_thresholds():
    body = "\n".join(f"        n += {i};" for i in range(40))
    project = project_of(body)
    assert "MAINT-01" in rules_of(project)
    assert "MAINT-01" not in rules_of(project, max_method_lines=100)
    branches = "\n".join(f"        if (n == {i}) {{ n++; }}" for i in range(12))
    assert "MAINT-09" in rules_of(project_of(branches))
    assert "MAINT-09" not in rules_of(project_of(branches), max_cyclomatic=20)


def test_maint_03_flags_deep_nesting_but_not_else_if_chains():
    deep = "if (n > 0) { for (String s : items) { while (n > 1) { if (s != null) { n--; } } } }"
    chain = "if (n == 1) { n++; } else if (n == 2) { n--; } else if (n == 3) { n = 0; } else if (n == 4) { n = 1; }"
    [finding] = rules_of(project_of(deep))["MAINT-03"]
    assert "4" in finding.title and finding.severity == "low"
    assert "MAINT-03" not in rules_of(project_of(chain))


def test_maint_04_flags_many_parameters():
    members = "void many(int a, int b, int c, int d, int e, int f) { }"
    assert "MAINT-04" in rules_of(project_of("n++;", members))
    assert "MAINT-04" not in rules_of(project_of("n++;", "void few(int a, int b) { }"))


def test_maint_02_finds_duplicates_up_to_names_and_literals():
    members = """
    int sumA(List<Integer> xs) {
        int total = 0;
        for (int x : xs) {
            if (x > 10) {
                total += x * 2;
            }
        }
        return total;
    }
    int sumB(List<Integer> ys) {
        int acc = 0;
        for (int y : ys) {
            if (y > 20) {
                acc += y * 3;
            }
        }
        return acc;
    }
    int other(List<Integer> zs) {
        return zs.size();
    }"""
    [finding] = rules_of(project_of("n++;", members))["MAINT-02"]
    assert finding.severity == "medium"
    assert "повторяются" in finding.explanation
    assert len(finding.evidence.static) == 2
    result = analyze(project_of("n++;", members))
    assert result.metrics.totals.duplication_percent > 30


def test_maint_02_ignores_tiny_repeated_statements():
    body = "n++; n++; n++; n++; n++; n++;"
    assert "MAINT-02" not in rules_of(project_of(body))


def test_maint_05_flags_big_and_incohesive_classes_but_not_data_classes():
    god = "\n".join(f"    int m{i}() {{ return f{i} + {i};\n    }}" for i in range(24))
    fields = "\n".join(f"    int f{i};" for i in range(24))
    assert "MAINT-05" in rules_of(project_of("n++;", f"{fields}\n{god}"))

    getters = "\n".join(f"    int get{i}() {{ return f{i}; }}" for i in range(10))
    data_fields = "\n".join(f"    int f{i};" for i in range(10))
    assert "MAINT-05" not in rules_of(project_of("n++;", f"{data_fields}\n{getters}"))


def test_findings_are_sorted_by_severity_complexity_and_line():
    body = """
        String r = "";
        for (String a : items) { r += a; for (String b : items) { if (a.equals(b)) { n++; } } }
        if (items.get(0) == "x") { n++; }"""
    findings = analyze(project_of(body)).findings
    order = {"high": 0, "medium": 1, "low": 2}
    keys = [(order[f.severity], f.location.start_line) for f in findings]
    assert [f.severity for f in findings][0] == "high"
    assert keys == sorted(keys, key=lambda k: (k[0], 0)) or keys[0][0] == 0
    ids = [f.id for f in findings]
    assert len(ids) == len(set(ids))


# --- сложность узла и фрагмента ------------------------------------------------------------------------------


def test_estimates_for_nodes_and_ranges():
    project = project_of(SLIDE_5)
    analysis = analyze(project)
    method_id = "A.java#A.run(List<String>, int)"
    assert estimate_node(project, analysis, method_id).current == "O(n²)"
    outer = estimate_node(project, analysis, f"{method_id}/foreach[0]")
    inner = estimate_node(project, analysis, f"{method_id}/foreach[0]/foreach[0]")
    assert (outer.current, inner.current) == ("O(n²)", "O(n)")
    assert outer.after == "O(n)"
    assert inner.after is None
    assert estimate_node(project, analysis, "A.java#A.nope()") is None
    assert estimate_node(project, analysis, f"{method_id}/foreach[9]") is None

    whole = estimate_range(project, analysis, "A.java", 7, 13)
    assert whole.current == "O(n²)"
    inside = estimate_range(project, analysis, "A.java", 8, 12)
    assert inside.current == "O(n)"
    assert estimate_range(project, analysis, "A.java", 1, 2).current == "O(1)"
    assert estimate_range(project, analysis, "Nope.java", 1, 2) is None


def test_program_complexity_and_expected_optimisation():
    result = analyze(project_of(SLIDE_5))
    assert result.complexity.current == "O(n²)"
    assert result.complexity.optimized == "O(n)"
    assert analyze(project_of("n++;")).complexity.optimized is None


# --- метрики ----------------------------------------------------------------------------------------------------


def test_metrics_for_a_method_with_known_values():
    members = """
    /** Комментарий не считается строкой кода. */
    int classify(int x, int y) {
        // однострочный комментарий

        if (x > 0 && y > 0) {
            for (int i = 0; i < x; i++) {
                if (i % 2 == 0) {
                    y += i;
                }
            }
        } else if (x < 0 || y < 0) {
            return -1;
        }
        switch (y) {
            case 1:
                return 1;
            case 2:
                return 2;
            default:
                break;
        }
        return x > y ? x : y;
    }"""
    metrics = analyze(project_of("n++;", members)).metrics
    method = next(m for m in metrics.methods if m.name == "classify")
    # 1 + if + && + for + if + else-if + || + 2 case + ?:
    assert method.cyclomatic == 10
    assert method.max_nesting == 3
    assert method.params == 2
    assert method.lines == 20  # без комментариев и пустых строк
    assert method.cognitive > method.cyclomatic - 5


def test_metrics_totals_and_lcom4():
    members = """
    int a; int b;
    int useA1() { int r = a; r++; r++; r++; return r; }
    int useA2() { int r = a; r--; r--; r--; return r; }
    int useB() { int r = b; r += 2; r += 3; r += 4; return r; }
    int getA() { return a; }
    """
    metrics = analyze(project_of("n++;", members)).metrics
    cls = next(t for t in metrics.types if t.name == "A")
    assert (cls.fields, cls.methods) == (2, 5)
    assert cls.lcom4 == 2  # {useA1, useA2} и {useB}; getA тривиален и не учитывается
    assert metrics.totals.files == 1 and metrics.totals.types == 1
    assert metrics.totals.methods == 5
    assert metrics.totals.cyclomatic_max >= 1
    assert metrics.totals.code_lines <= metrics.totals.lines


# --- корпус -------------------------------------------------------------------------------------------------------


def load(directory: Path) -> JavaProject:
    return JavaProject(
        {
            p.relative_to(directory).as_posix(): p.read_text(encoding="utf-8")
            for p in sorted(directory.rglob("*.java"))
        }
    )


def test_analyzer_pairs_sample_gives_the_slide_5_finding():
    result = analyze(load(SAMPLES / "analyzer-pairs"))
    perf = [f for f in result.findings if f.rule_id == "PERF-01"]
    assert len(perf) == 1
    assert perf[0].complexity.current == "O(n²)" and perf[0].complexity.after == "O(n)"
    assert perf[0].location.file == "Analyzer.java"
    assert result.complexity.current == "O(n²)"


def test_demo_orders_has_the_planted_defects_within_the_time_budget():
    project = load(SAMPLES / "demo-orders")
    started = time.perf_counter()
    result = analyze(project)
    assert time.perf_counter() - started < 1.0  # бюджет анализа 1000 строк (S7.9)
    methods = {f.location.method_id.split(".")[-1] for f in result.findings if f.location.method_id}
    assert {"mergeDuplicates()", "distinctCustomers()", "buildCsv()"} <= methods
    rules = {f.rule_id for f in result.findings}
    assert {
        "PERF-01",
        "PERF-02",
        "PERF-03",
        "BUG-01",
        "BUG-02",
        "MAINT-01",
        "MAINT-02",
        "MAINT-05",
    } <= rules
    for finding in result.findings:
        assert finding.explanation and finding.recommendation and finding.location.file
        if finding.category == "PERF":
            assert finding.complexity is not None and finding.complexity.contributions


@pytest.mark.parametrize(
    "directory",
    sorted(p for p in (SAMPLES / "monoliths").iterdir() if p.is_dir())
    + [p for p in (SAMPLES / "scope").iterdir() if p.is_dir()],
    ids=lambda p: p.name,
)
def test_analysis_is_deterministic_and_never_crashes_on_the_corpus(directory: Path):
    files = list(directory.rglob("*.java"))
    if not files:
        pytest.skip("пустой каталог")
    first = analyze(load(directory))
    second = analyze(JavaProject(load(directory).files))
    assert [f.id for f in first.findings] == [f.id for f in second.findings]
    assert first.complexity == second.complexity
    assert len({f.id for f in first.findings}) == len(first.findings)
