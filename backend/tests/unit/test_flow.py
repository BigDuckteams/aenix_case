"""Содержимое блоков блок-схемы: данные по видам, бейджи, вызовы, лямбды, конвейеры (S2.5, S2.7)."""

from __future__ import annotations

from engine.graph.model import FlowGraph, FlowNode
from tests.unit.engine_helpers import flow_of, project_of, wrap_method


def body_flow(body: str, header: str = "void run()", extra: str = "") -> FlowGraph:
    source = wrap_method("        " + body, header)
    if extra:
        source = source.rstrip().removesuffix("}") + extra + "\n}\n"
    return flow_of(source, header.split()[-1] if "(" in header else "run()")


def node(graph: FlowGraph, kind: str, index: int = 0) -> FlowNode:
    return [n for n in graph.nodes if n.kind == kind][index]


def kinds(graph: FlowGraph) -> list[str]:
    return [n.kind for n in graph.nodes]


# --- данные блоков -------------------------------------------------------------------------------


def test_var_decl_keeps_every_declarator_in_one_block():
    graph = body_flow("int a = 1, b[] = {2}; var s = new StringBuilder(); final String t = null;")
    first, second, third = (n for n in graph.nodes if n.kind == "var_decl")
    assert first.data["type"] == "int"
    assert first.data["names"] == ["a", "b"]
    assert first.data["declarators"][1] == {"name": "b", "dims": "[]", "init": "{2}"}
    assert second.data["type"] == "var"
    assert third.data["modifiers"] == ["final"]
    assert third.data["declarators"][0]["init"] == "null"


def test_assignments_and_updates_are_assign_blocks():
    graph = body_flow("x = 1; x += 2; x++; --y; a[0] = 3; this.f = 4; foo();")
    assigns = [n for n in graph.nodes if n.kind == "assign"]
    assert [(n.data["target"], n.data["op"]) for n in assigns] == [
        ("x", "="),
        ("x", "+="),
        ("x", "++"),
        ("y", "--"),
        ("a[0]", "="),
        ("this.f", "="),
    ]
    assert assigns[1].data["value"] == "2"
    assert node(graph, "operation").data["expr"] == "foo()"


def test_condition_and_loops_carry_their_headers():
    graph = body_flow(
        "if (a > 0 && b < 2) { x(); }\n"
        "        for (int i = 0, j = 9; i < j; i++, j--) { y(); }\n"
        "        for (String s : names) { z(s); }\n"
        "        while (k > 0) { k--; }\n"
        "        do { k++; } while (k < 5);"
    )
    assert node(graph, "condition").data["expr"] == "a > 0 && b < 2"
    assert node(graph, "condition").code == "if (a > 0 && b < 2)"
    classic = node(graph, "loop_for")
    assert classic.data == {"init": ["int i = 0, j = 9"], "cond": "i < j", "update": ["i++", "j--"]}
    foreach = node(graph, "loop_foreach")
    assert foreach.data == {"type": "String", "name": "s", "iterable": "names"}
    assert foreach.code == "for (String s : names)"
    plain, do_while = (n for n in graph.nodes if n.kind == "loop_while")
    assert plain.data == {"cond": "k > 0", "do_while": False}
    assert do_while.data == {"cond": "k < 5", "do_while": True}


def test_switch_labels_and_style():
    graph = body_flow("switch (a) { case 1, 2 -> f(); default -> g(); }")
    switch = node(graph, "switch")
    assert switch.data == {"expr": "a", "style": "arrow"}
    case, default = (n for n in graph.nodes if n.kind == "case")
    assert case.data == {"labels": ["1, 2"], "default": False}
    assert default.data == {"labels": ["default"], "default": True}
    edges = {(e.label, e.target.rsplit("/", 1)[-1]) for e in graph.edges if e.kind == "case"}
    assert edges == {("1, 2", "case[0]"), ("default", "case[1]")}


def test_try_data_catch_types_and_resources():
    graph = body_flow(
        "try (Scanner in = new Scanner(System.in); var q = open()) { a(); }"
        " catch (IOException | IllegalStateException e) { b(); } finally { c(); }"
    )
    try_node = node(graph, "try")
    assert try_node.data["resources"] == [
        {"type": "Scanner", "name": "in", "init": "new Scanner(System.in)"},
        {"type": "var", "name": "q", "init": "open()"},
    ]
    catch = node(graph, "catch")
    assert catch.data == {"types": ["IOException", "IllegalStateException"], "name": "e"}
    assert catch.code == "catch (IOException | IllegalStateException e)"
    assert node(graph, "finally").parent_id == try_node.id


def test_jump_blocks_know_their_labels():
    graph = body_flow("a: while (true) { if (x) break a; else continue a; }")
    assert node(graph, "labeled").data == {"label": "a"}
    assert node(graph, "break").data == {"label": "a"}
    assert node(graph, "continue").data == {"label": "a"}
    loop = node(graph, "loop_while")
    continue_edge = next(e for e in graph.edges if e.kind == "continue")
    assert continue_edge.target == loop.id


def test_return_throw_yield_expressions():
    graph = body_flow(
        'if (a) return 1; else throw new IllegalStateException("x");', header="int run()"
    )
    assert node(graph, "return").data == {"expr": "1"}
    thrown = node(graph, "throw")
    assert thrown.data["type"] == "IllegalStateException"
    assert [b.label for b in thrown.badges] == ["IllegalStateException"]
    assert set(graph.exits) == {node(graph, "return").id, thrown.id}


def test_method_node_describes_the_member():
    source = """
import java.io.IOException;
public class Main {
    @Override
    public static <T> List<T> pick(int n, String... names) throws IOException {
        return null;
    }
}
"""
    graph = flow_of(source, "pick(int, String...)")
    root = graph.nodes[0]
    assert root.kind == "method" and root.label == "Метод"
    assert root.data["name"] == "pick"
    assert root.data["return_type"] == "List<T>"
    assert root.data["params"] == [
        {"type": "int", "name": "n"},
        {"type": "String...", "name": "names"},
    ]
    assert root.data["throws"] == ["IOException"]
    assert root.data["type_params"] == ["T"]
    assert "public" in root.data["modifiers"] and "static" in root.data["modifiers"]
    assert graph.signature == "pick(int, String...)"


# --- бейджи ввода и вывода -----------------------------------------------------------------------


def badge_kinds(graph: FlowGraph, kind: str, index: int = 0) -> list[str]:
    return [b.kind for b in node(graph, kind, index).badges]


def test_output_and_error_badges():
    graph = body_flow(
        'System.out.println("a"); System.out.printf("%d%n", 1); System.err.println("e"); System.out.print(1);'
    )
    ops = [n for n in graph.nodes if n.kind == "operation"]
    assert [[b.kind for b in n.badges] for n in ops] == [
        ["output"],
        ["output"],
        ["error_output"],
        ["output"],
    ]
    assert ops[2].badges[0].label == "ошибка"


def test_input_badges_follow_declared_receiver_types():
    graph = body_flow(
        "Scanner in = new Scanner(System.in);\n"
        "        int n = in.nextInt();\n"
        "        BufferedReader r = new BufferedReader(new InputStreamReader(System.in));\n"
        "        String line = r.readLine();\n"
        "        String other = list.next();"
    )
    decls = [n for n in graph.nodes if n.kind == "var_decl"]
    assert [[b.kind for b in n.badges] for n in decls] == [
        ["input"],
        ["input"],
        ["input"],
        ["input"],
        [],
    ]


def test_plain_calls_have_no_io_badges():
    graph = body_flow("int n = list.size(); log(n);")
    assert all(not n.badges for n in graph.nodes)


# --- вызовы методов проекта ------------------------------------------------------------------------

CALLS = """
interface Shape { double area(); }
class Circle implements Shape { public double area() { return 3; } }
class Square implements Shape { public double area() { return 4; } }
class Base { void hello() {} static int util(int x) { return x; } }
class Child extends Base {
    void hello() { super.hello(); }
    void other(int a) {}
    void other(int a, int b) {}
    void other(String... rest) {}
    Child(int a) {}
    Child() { this(1); }
}
public class Main {
    Shape shape;
    Child child = new Child();
    int count;
    void helper() {}
    void run(Shape s, Base b) {
        helper();
        this.helper();
        s.area();
        shape.area();
        b.hello();
        child.other(1);
        child.other(1, 2);
        child.other("a", "b", "c");
        Base.util(3);
        new Child(5);
        new Thread();
        list.add(1);
        String text = String.valueOf(count);
        child.hello();
    }
}
"""


def call_targets(graph: FlowGraph) -> list[str]:
    return [t for n in graph.nodes for t in n.data.get("calls", [])]


def test_call_resolution_by_name_arity_and_declared_type():
    graph = flow_of(CALLS, "run(Shape, Base)")
    ops = [n for n in graph.nodes if n.kind in {"operation", "var_decl"}]
    by_expr = {n.data.get("expr") or n.code: n for n in ops}

    def targets(expr: str) -> list[str]:
        return [t.split("#", 1)[1] for t in by_expr[expr].data.get("calls", [])]

    assert targets("helper()") == ["Main.helper()"]
    assert targets("this.helper()") == ["Main.helper()"]
    # через интерфейс — все реализации
    assert sorted(targets("s.area()")) == ["Circle.area()", "Shape.area()", "Square.area()"]
    assert sorted(targets("shape.area()")) == ["Circle.area()", "Shape.area()", "Square.area()"]
    # перегрузка по арности; varargs принимает любое число
    assert targets("child.other(1)") == ["Child.other(int)", "Child.other(String...)"]
    assert targets("child.other(1, 2)") == ["Child.other(int, int)", "Child.other(String...)"]
    assert targets('child.other("a", "b", "c")') == ["Child.other(String...)"]
    # статический вызов по имени типа, конструктор, внешние вызовы без ребра
    assert targets("Base.util(3)") == ["Base.util(int)"]
    assert targets("new Child(5)") == ["Child.Child(int)"]
    assert targets("new Thread()") == []
    assert targets("list.add(1)") == []
    assert [t for t in by_expr["String text = String.valueOf(count);"].data.get("calls", [])] == []
    # виртуальный вызов базового типа видит переопределение в подтипе
    assert sorted(targets("b.hello()")) == ["Base.hello()", "Child.hello()"]


def test_call_badges_and_call_edges_point_to_member_ids():
    graph = flow_of(CALLS, "run(Shape, Base)")
    helper = next(n for n in graph.nodes if n.data.get("expr") == "helper()")
    assert [(b.kind, b.label) for b in helper.badges] == [("call", "helper()")]
    assert helper.badges[0].ref == "Main.java#Main.helper()"
    call_edges = [e for e in graph.edges if e.kind == "call" and e.source == helper.id]
    assert [e.target for e in call_edges] == ["Main.java#Main.helper()"]
    area = next(n for n in graph.nodes if n.data.get("expr") == "s.area()")
    assert area.badges[0].label == "area() ×3"


def test_super_and_explicit_constructor_calls():
    child_hello = flow_of(CALLS, "hello()", owner="Child")
    assert call_targets(child_hello) == ["Main.java#Base.hello()"]
    ctor = flow_of(CALLS, "Child()", owner="Child")
    assert call_targets(ctor) == ["Main.java#Child.Child(int)"]


# --- лямбды, анонимные и локальные типы, конвейеры ----------------------------------------------


def test_lambda_cards_expression_and_block():
    graph = body_flow("list.forEach(v -> use(v));\n        Runnable r = () -> { go(); return; };")
    expression, block = (n for n in graph.nodes if n.kind == "lambda")
    assert expression.data == {"params": ["v"], "body_kind": "expression"}
    assert expression.code.startswith("v ->")
    assert expression.parent_id == node(graph, "operation").id
    assert block.data == {"params": [], "body_kind": "block"}
    inside = [n for n in graph.nodes if n.parent_id == block.id]
    assert [n.kind for n in inside] == ["operation", "return"]
    # return внутри лямбды — не выход из метода
    assert node(graph, "var_decl").id in graph.exits


def test_nested_lambda_hosts():
    graph = body_flow("Function<Integer, Function<Integer, Integer>> f = a -> b -> a + b;")
    outer, inner = (n for n in graph.nodes if n.kind == "lambda")
    assert inner.parent_id == outer.id
    assert outer.data["params"] == ["a"] and inner.data["params"] == ["b"]


def test_anonymous_and_local_types():
    graph = body_flow(
        'Object o = new Object() { public String toString() { return "a"; } int n; };\n'
        "        class Local { void f() {} }\n"
        "        record P(int x) {}"
    )
    anonymous, local_class, local_record = (n for n in graph.nodes if n.kind == "local_type")
    assert anonymous.data["type_kind"] == "anonymous"
    assert anonymous.data["base"] == "Object"
    assert anonymous.data["members"] == ["toString()", "n"]
    assert anonymous.parent_id == node(graph, "var_decl").id
    assert (local_class.data["type_kind"], local_class.data["name"]) == ("class", "Local")
    assert local_class.data["members"] == ["f()"]
    assert (local_record.data["type_kind"], local_record.data["name"]) == ("record", "P")
    assert local_class.parent_id is None


def test_stream_pipeline_stages():
    graph = body_flow(
        "int total = items.stream().filter(i -> i.ok()).mapToInt(Item::price).sum();\n"
        "        IntStream.range(0, 3).boxed().collect(Collectors.toList());\n"
        "        String s = names.get(0).trim();"
    )
    decls = [n for n in graph.nodes if n.kind in {"var_decl", "operation"}]
    pipelines = [n.data.get("pipelines") for n in decls]
    assert [s["name"] for s in pipelines[0][0]] == ["stream", "filter", "mapToInt", "sum"]
    assert pipelines[0][0][1]["args"] == "(i -> i.ok())"
    assert [s["name"] for s in pipelines[1][0]] == ["range", "boxed", "collect"]
    assert pipelines[2] is None


def test_switch_expression_inside_declaration_becomes_a_card_with_yield():
    graph = body_flow("int r = switch (a) { case 1 -> f(); default -> { yield g(); } };")
    assert kinds(graph) == ["method", "var_decl", "switch", "case", "operation", "case", "yield"]
    switch = node(graph, "switch")
    assert switch.parent_id == node(graph, "var_decl").id
    assert switch.data == {"expr": "a", "style": "arrow"}
    # карточка не соединена с потоком метода: ребра идут только внутри неё
    inside = {n.id for n in graph.nodes if n.id.startswith(switch.id)}
    flow_edges = [e for e in graph.edges if e.source in inside or e.target in inside]
    assert all(e.source in inside and e.target in inside for e in flow_edges)
    assert graph.exits == [node(graph, "var_decl").id]


# --- устойчивость -----------------------------------------------------------------------------------


def test_unknown_statements_become_code_blocks_not_losses():
    project = project_of(wrap_method("        int a = ;\n        foo(;\n        ok();"))
    graph = project.flow("Main.java#Main.run()")
    assert graph is not None
    assert graph.nodes[0].kind == "method"
    text = " ".join(n.code for n in graph.nodes)
    assert "ok()" in text


def test_every_node_id_is_unique_and_prefixed_with_the_member():
    graph = flow_of(CALLS, "run(Shape, Base)")
    ids = [n.id for n in graph.nodes]
    assert len(ids) == len(set(ids))
    assert all(i == graph.method_id or i.startswith(graph.method_id + "/") for i in ids)
