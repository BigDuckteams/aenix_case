"""Декларации: пакеты, импорты, типы и члены (S2.2)."""

from __future__ import annotations

import pytest

from engine.java.symbols import FileSymbols, Member, TypeDecl, base_name
from tests.unit.engine_helpers import project_of

SOURCE = """
package demo.shop;

import java.util.*;
import static java.lang.Math.max;

@Deprecated
public abstract class Base<T extends Comparable<T>, U> extends Parent<T> implements Runnable, Comparable<Base<T, U>> {
    public static final int LIMIT = 10, OTHER;
    private final List<String> names = new ArrayList<>();
    int[] data, matrix[];
    static { init(); }
    static { more(); }
    { setup(); }
    protected Base(int a, String... rest) throws java.io.IOException, IllegalStateException { this(a); }
    Base() { }
    @Override
    public <R> R convert(Map<String, List<Integer>> input, R fallback) throws Exception { return fallback; }
    abstract void todo();
    public static void main(String[] args) { }
    enum Level { LOW, HIGH }
    interface Visitor { void visit(); default int count() { return 0; } }
    static class Inner { class Deep { void f() {} } }
}

record Point(int x, int y) implements Shape {
    static final Point ORIGIN = new Point(0, 0);
    Point { if (x < 0) throw new IllegalArgumentException(); }
    double dist() { return 0; }
}

enum Color {
    RED("r") { @Override String label() { return "red"; } },
    GREEN("g");
    private final String code;
    Color(String code) { this.code = code; }
    String label() { return code; }
}

interface Shape extends Comparable<Shape>, java.io.Serializable {
    int SIDES = 4;
    double area();
    default String describe() { return ""; }
    static Shape unit() { return null; }
    private void hidden() { }
}
"""


@pytest.fixture(scope="module")
def symbols() -> FileSymbols:
    return project_of(SOURCE).symbols("Main.java")


def by_path(symbols: FileSymbols, path: str) -> TypeDecl:
    return next(t for t in symbols.all_types() if t.path == path)


def member(decl: TypeDecl, key: str) -> Member:
    return next(m for m in decl.members if m.key == key)


def test_package_imports_and_type_inventory(symbols):
    assert symbols.package == "demo.shop"
    assert symbols.imports == ("java.util.*", "static java.lang.Math.max")
    assert [t.name for t in symbols.types] == ["Base", "Point", "Color", "Shape"]
    assert [t.path for t in symbols.all_types()] == [
        "Base",
        "Base.Level",
        "Base.Visitor",
        "Base.Inner",
        "Base.Inner.Deep",
        "Point",
        "Color",
        "Shape",
    ]
    assert by_path(symbols, "Base.Inner.Deep").parent_path == "Base.Inner"
    assert by_path(symbols, "Base").id == "Main.java#Base"


def test_class_header_generics_and_inheritance(symbols):
    base = by_path(symbols, "Base")
    assert base.kind == "class"
    assert base.modifiers == ("public", "abstract")
    assert base.annotations == ("Deprecated",)
    assert base.type_params == ("T extends Comparable<T>", "U")
    assert base.extends == ("Parent<T>",)
    assert base.implements == ("Runnable", "Comparable<Base<T, U>>")


def test_interface_extends_and_record_enum_details(symbols):
    shape = by_path(symbols, "Shape")
    assert shape.kind == "interface"
    assert shape.extends == ("Comparable<Shape>", "java.io.Serializable")
    point = by_path(symbols, "Point")
    assert point.kind == "record"
    assert [(c.name, c.type) for c in point.components] == [("x", "int"), ("y", "int")]
    assert point.implements == ("Shape",)
    color = by_path(symbols, "Color")
    assert color.kind == "enum" and color.constants == ("RED", "GREEN")


def test_fields_one_member_per_declarator(symbols):
    base = by_path(symbols, "Base")
    limit, other = member(base, "LIMIT"), member(base, "OTHER")
    assert (limit.type_text, other.type_text) == ("int", "int")
    assert limit.modifiers == ("public", "static", "final")
    assert member(base, "names").type_text == "List<String>"
    assert member(base, "data").type_text == "int[]"
    assert member(base, "matrix").type_text == "int[][]"
    assert limit.id == "Main.java#Base.LIMIT"
    assert limit.kind == "field" and limit.role == "field"


def test_constructors_methods_and_keys(symbols):
    base = by_path(symbols, "Base")
    ctor = member(base, "Base(int, String...)")
    assert ctor.kind == "constructor"
    assert [(p.name, p.type, p.varargs) for p in ctor.params] == [
        ("a", "int", False),
        ("rest", "String...", True),
    ]
    assert ctor.throws == ("java.io.IOException", "IllegalStateException")
    assert member(base, "Base()").params == ()
    convert = member(base, "convert(Map<String, List<Integer>>, R)")
    assert convert.type_text == "R" and convert.type_params == ("R",)
    assert convert.annotations == ("Override",)
    assert convert.throws == ("Exception",)
    assert member(base, "todo()").has_body is False
    assert convert.id == "Main.java#Base.convert(Map<String, List<Integer>>, R)"


def test_initializers_are_numbered_per_kind(symbols):
    base = by_path(symbols, "Base")
    inits = [m for m in base.members if m.kind == "initializer"]
    assert [(m.key, m.role, m.is_static) for m in inits] == [
        ("<clinit>[0]", "static_init", True),
        ("<clinit>[1]", "static_init", True),
        ("<init>[0]", "init", False),
    ]


def test_record_components_compact_constructor_and_enum_constants(symbols):
    point = by_path(symbols, "Point")
    roles = {m.key: m.role for m in point.members}
    assert roles["x"] == "component" and roles["y"] == "component"
    assert roles["Point(int, int)"] == "compact_constructor"
    assert roles["ORIGIN"] == "field"
    assert roles["dist()"] == "method"
    color = by_path(symbols, "Color")
    assert {m.key: m.role for m in color.members} == {
        "RED": "constant",
        "GREEN": "constant",
        "code": "field",
        "Color(String)": "constructor",
        "label()": "method",
    }
    assert member(color, "RED").is_static


def test_interface_members_get_implicit_modifiers(symbols):
    shape = by_path(symbols, "Shape")
    assert set(member(shape, "SIDES").modifiers) >= {"static", "final"}
    assert "abstract" in member(shape, "area()").modifiers
    assert "abstract" not in member(shape, "describe()").modifiers
    assert "public" in member(shape, "describe()").modifiers
    assert "private" in member(shape, "hidden()").modifiers
    visitor = by_path(symbols, "Base.Visitor")
    assert [m.key for m in visitor.members] == ["visit()", "count()"]


def test_main_classes_are_qualified(symbols):
    assert symbols.main_classes == ("demo.shop.Base",)


def test_two_main_classes_and_default_package():
    source = (
        "class A { public static void main(String[] a) {} }\n"
        "class B { static void main(String... args) {} public static void main(String[] args) {} }\n"
    )
    assert project_of(source).main_classes() == ["A", "B"]


def test_overloads_have_distinct_ids():
    project = project_of("class A { void f(int a) {} void f(long a) {} void f(int a, int b) {} }")
    ids = [m.id for m in project.members()]
    assert len(ids) == len(set(ids)) == 3


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("List<String>", "List"),
        ("java.util.Map.Entry<K, V>", "Entry"),
        ("int[]", "int"),
        ("String...", "String"),
        ("Outer.Inner", "Inner"),
    ],
)
def test_base_name(text, expected):
    assert base_name(text) == expected
