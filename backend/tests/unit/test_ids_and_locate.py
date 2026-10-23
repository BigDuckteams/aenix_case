"""Структурные ID: формат, стабильность при правках выше и поиск узла по позиции (S2.6)."""

from __future__ import annotations

from pathlib import Path

from engine.graph.ids import PathScope, node_depth, split_node_id
from engine.java.project import JavaProject
from tests.unit.engine_helpers import project_of

REPO = Path(__file__).resolve().parents[3]

SOURCE = """public class Main {
    int total;

    int sum(int[] values) {
        int result = 0;
        for (int v : values) {
            if (v > 0) {
                result += v;
            } else {
                result -= v;
            }
        }
        return result;
    }

    void greet(String name) {
        System.out.println("Привет, " + name + "!");
    }
}
"""


def all_ids(project: JavaProject) -> list[str]:
    return [n.id for g in project.flows() for n in g.nodes]


def test_id_format_follows_the_documented_scheme():
    graph = project_of(SOURCE).flow("Main.java#Main.sum(int[])")
    assert graph is not None
    ids = [n.id for n in graph.nodes]
    assert ids[0] == "Main.java#Main.sum(int[])"
    assert "Main.java#Main.sum(int[])/foreach[0]/if[0]/then/assign[0]" in ids
    assert "Main.java#Main.sum(int[])/foreach[0]/if[0]/else/assign[0]" in ids
    assert "Main.java#Main.sum(int[])/return[0]" in ids


def test_split_node_id_and_depth():
    member, path = split_node_id("Main.java#Main.sum(int[])/foreach[0]/if[0]/then/assign[0]")
    assert member == "Main.java#Main.sum(int[])"
    assert path == ("foreach[0]", "if[0]", "then", "assign[0]")
    assert split_node_id("Main.java#Main.sum(int[])") == ("Main.java#Main.sum(int[])", ())
    assert node_depth("Main.java#Main.sum(int[])/foreach[0]/if[0]/then/assign[0]") == 3
    assert node_depth("Main.java#Main.sum(int[])") == 0


def test_path_scope_counts_neighbours_independently():
    scope = PathScope()
    assert [scope.next("op"), scope.next("if"), scope.next("op")] == ["op[0]", "if[0]", "op[1]"]
    inner = scope.child("then")
    assert inner.next("op") == "then/op[0]"
    assert PathScope(prefix="foreach[0]/").next("op") == "foreach[0]/op[0]"


def test_ids_survive_blank_lines_and_comments_above():
    original = project_of(SOURCE)
    shifted_source = "// шапка файла\n\n\n/* лицензия */\n" + SOURCE.replace(
        "    int total;", "    // поле\n    int total;\n\n\n"
    ).replace("        for (int v", "        // обход\n        for (int v")
    shifted = project_of(shifted_source)
    assert all_ids(original) == all_ids(shifted)
    old = original.flow("Main.java#Main.sum(int[])")
    new = shifted.flow("Main.java#Main.sum(int[])")
    assert old is not None and new is not None
    assert [n.range.start_line for n in old.nodes] != [n.range.start_line for n in new.nodes]


def test_ids_change_only_for_the_edited_method():
    before = project_of(SOURCE)
    after = project_of(SOURCE.replace("result += v;", "result += v;\n                count();"))
    greet = "Main.java#Main.greet(String)"
    assert [n.id for n in before.flow(greet).nodes] == [n.id for n in after.flow(greet).nodes]
    sum_before = {n.id for n in before.flow("Main.java#Main.sum(int[])").nodes}
    sum_after = {n.id for n in after.flow("Main.java#Main.sum(int[])").nodes}
    assert sum_after - sum_before == {"Main.java#Main.sum(int[])/foreach[0]/if[0]/then/op[0]"}
    assert sum_before <= sum_after


def test_locate_picks_the_deepest_block_under_the_cursor():
    project = project_of(SOURCE)
    base = "Main.java#Main.sum(int[])"
    # строка 8 — `result += v;` внутри then-ветки
    location = project.locate("Main.java", 8, 20)
    assert location is not None
    assert location.method_id == base
    assert location.node_id == f"{base}/foreach[0]/if[0]/then/assign[0]"
    # заголовок цикла — сам цикл
    assert project.locate("Main.java", 6, 12).node_id == f"{base}/foreach[0]"
    # условие — блок условия, а не цикл
    assert project.locate("Main.java", 7, 14).node_id == f"{base}/foreach[0]/if[0]"
    # пустая строка внутри метода — корень метода
    assert project.locate("Main.java", 4, 6).node_id == base


def test_locate_outside_methods_and_files():
    project = project_of(SOURCE)
    field = project.locate("Main.java", 2, 9)
    assert field is not None and field.node_id == "Main.java#Main.total" and field.method_id is None
    assert project.locate("Main.java", 1, 1).node_id == "Main.java#Main"
    assert project.locate("Nope.java", 1, 1) is None


def test_locate_uses_utf16_columns_for_cyrillic_and_emoji():
    project = project_of(SOURCE.replace('"Привет, "', '"Привет 😀, "'))
    graph = project.flow("Main.java#Main.greet(String)")
    op = next(n for n in graph.nodes if n.kind == "operation")
    assert op.range.start_col == 9
    # колонка конца строки считается в UTF-16: эмодзи занимает две единицы
    line = project.files["Main.java"].splitlines()[op.range.start_line - 1]
    utf16_len = len(line.encode("utf-16-le")) // 2
    assert op.range.end_col == utf16_len + 1
    inside = project.locate("Main.java", op.range.start_line, op.range.end_col - 5)
    assert inside is not None and inside.node_id == op.id


def test_demo_orders_every_node_is_locatable():
    source = (REPO / "samples" / "demo-orders" / "Main.java").read_text(encoding="utf-8")
    project = JavaProject({"Main.java": source})
    checked = 0
    for graph in project.flows():
        for n in graph.nodes:
            found = project.locate("Main.java", n.range.start_line, n.range.start_col)
            assert found is not None and found.method_id == graph.method_id
            # на самой первой позиции блока лежит он сам или более вложенный блок с тем же началом
            assert (
                found.node_id == n.id
                or found.node_id.startswith(n.id + "/")
                or found.node_id == graph.method_id
            )
            checked += 1
    assert checked > 500
