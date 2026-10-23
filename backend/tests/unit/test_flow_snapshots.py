"""Снапшоты блок-схем на каждый вид оператора (S2.5, docs/10 § 3.1).

Эталоны лежат в ``tests/snapshots/flow/`` и просмотрены вручную; обновление —
``UPDATE_SNAPSHOTS=1 uv run pytest tests/unit/test_flow_snapshots.py`` с последующим осмотром diff.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.engine_helpers import assert_snapshot, flow_of, render, wrap_method

REPO = Path(__file__).resolve().parents[3]

CASES: dict[str, str] = {
    "if-else-if": "if (a > 0) { x(); } else if (a < 0) { y(); } else { z(); }\n        w();",
    "if-no-else": "if (a > 0) { x(); }\n        w();",
    "for-continue": "for (int i = 0; i < 3; i++) { if (i == 1) continue; x(i); }",
    "foreach-break": "for (String s : list) { if (s == null) break; use(s); }\n        done();",
    "while-and-do-while": "while (a > 0) { a--; }\n        do { b++; } while (b < 5);",
    "switch-classic-fallthrough": "switch (a) { case 1: case 2: foo(); break; case 3: bar(); default: baz(); }\n        end();",
    "switch-arrow": "switch (a) { case 1 -> foo(); case 2 -> { bar(); } default -> throw new IllegalStateException(); }",
    "switch-without-default": "switch (a) { case 1: foo(); break; case 2: bar(); }\n        end();",
    "try-catch-finally": "try { a(); throw new IOException(); } catch (IOException e) { b(); } catch (Exception e) { c(); } finally { d(); }\n        after();",
    "try-with-resources": "try (Scanner in = new Scanner(System.in)) { in.nextInt(); }",
    "try-return-finally": "try { return; } finally { cleanup(); }",
    "nested-try-throw": "try { try { throw new IllegalStateException(); } catch (IOException e) { a(); } } catch (RuntimeException e) { b(); }",
    "labeled-break-continue": "outer: for (int i = 0; i < 3; i++) { for (int j = 0; j < 3; j++) { if (j == 2) continue outer; if (i == 2) break outer; } }\n        end();",
    "lambda-expression-and-block": "list.forEach(v -> System.out.println(v));\n        Runnable r = () -> { go(); return; };",
    "nested-lambda": "Function<Integer, Function<Integer, Integer>> f = a -> b -> a + b;",
    "anonymous-and-local-class": 'Object o = new Object() { public String toString() { return "a"; } };\n        class Local { void f() {} }',
    "stream-pipeline": "List<Integer> r = list.stream().filter(x -> x > 0).map(x -> x * 2).collect(Collectors.toList());",
    "switch-expression-in-declaration": "int r = switch (a) { case 1 -> 10; default -> { yield 0; } };\n        use(r);",
    "sync-and-assert": 'synchronized (this) { x = 1; }\n        assert a > 0 : "m";',
    "empty-method": "",
    "return-in-the-middle": "if (a) return;\n        x();",
    "throw-without-catch": "if (a) throw new IllegalArgumentException(); \n        x();",
    "assign-forms": "x = 1; x += 2; x++; --y; a[0] = 3; this.f = 4;",
    "var-forms": "int a = 1, b[] = {2}; var s = new StringBuilder(); final String t = null;",
    "multiple-update-for": "for (int i = 0, j = 10; i < j; i++, j--) { swap(i, j); }",
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_flow_snapshot(name: str):
    graph = flow_of(wrap_method("        " + CASES[name]), "run()")
    assert_snapshot(f"flow/{name}", render(graph))


def test_demo_orders_merge_duplicates_snapshot():
    """Метод из демо-монолита: цикл в цикле, условие, `break`, вызовы методов проекта."""
    from engine.java.project import JavaProject

    source = (REPO / "samples" / "demo-orders" / "Main.java").read_text(encoding="utf-8")
    graph = JavaProject({"Main.java": source}).flow("Main.java#Main.mergeDuplicates()")
    assert graph is not None
    assert_snapshot("flow/demo-orders-merge-duplicates", render(graph))


def test_constructor_and_initializers_snapshot():
    source = """
public class Main {
    static int count;
    int id;
    static { count = 0; }
    { id = 1; }
    Main(int id) { this(); this.id = id; }
    Main() { super(); count++; }
    abstract static class Shape { abstract double area(); }
}
"""
    parts = []
    from tests.unit.engine_helpers import project_of

    project = project_of(source)
    for member in project.members():
        graph = project.flow(member.id)
        if graph is not None:
            parts.append(f"## {member.id}\n{render(graph)}")
    assert_snapshot("flow/constructors-and-initializers", "\n".join(parts))
