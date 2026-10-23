"""Спайк S0.7: tree-sitter-java разбирает Java 21, ошибки видны, диапазоны верны для Monaco."""

from engine.graph.ranges import Position
from engine.java.ts import JAVA_LANGUAGE, parse

JAVA21 = """\
package demo;

import java.util.*;
import java.util.stream.Collectors;

public class Main {
    record Point(int x, int y) {
        Point {
            if (x < 0) throw new IllegalArgumentException("x");
        }
    }

    enum Color {
        RED("r") { @Override String label() { return "red"; } },
        GREEN("g");

        private final String code;
        Color(String code) { this.code = code; }
        String label() { return code; }
    }

    sealed interface Shape permits Circle, Square {}
    record Circle(double r) implements Shape {}
    record Square(double a) implements Shape {}

    static <T extends Comparable<T>> T max(List<? extends T> items) {
        T best = null;
        for (T item : items) {
            if (best == null || item.compareTo(best) > 0) best = item;
        }
        return best;
    }

    static double area(Shape s) {
        return switch (s) {
            case Circle c -> Math.PI * c.r() * c.r();
            case Square q -> q.a() * q.a();
        };
    }

    public static void main(String[] args) {
        var names = List.of("b", "a", "c");
        Map<String, Long> counts = names.stream()
            .filter(n -> !n.isEmpty())
            .collect(Collectors.groupingBy(String::toUpperCase, Collectors.counting()));
        Runnable r = () -> System.out.println(counts);
        r.run();
        int day = 3;
        String name = switch (day) {
            case 1, 7 -> "weekend";
            default -> {
                yield "weekday";
            }
        };
        System.out.printf("%s %d%n", name, day);
    }
}
"""


def find_all(parsed, type_name):
    """Все узлы типа ``type_name`` в порядке следования в тексте."""
    found = []
    stack = [parsed.root]
    while stack:
        node = stack.pop()
        if node.type == type_name:
            found.append(node)
        stack.extend(node.children)
    return sorted(found, key=lambda n: n.start_byte)


def test_java21_parses_without_errors():
    parsed = parse(JAVA21)
    assert parsed.ok, parsed.issues
    assert len(find_all(parsed, "record_declaration")) == 3  # Point, Circle, Square
    assert len(find_all(parsed, "enum_declaration")) == 1
    assert len(find_all(parsed, "lambda_expression")) == 2
    assert len(find_all(parsed, "switch_expression")) == 2
    assert len(find_all(parsed, "method_reference")) == 1
    assert len(find_all(parsed, "compact_constructor_declaration")) == 1
    assert find_all(parsed, "type_parameters")


def test_broken_file_reports_issues_with_positions():
    parsed = parse("class A {\n    void f() {\n        int x = ;\n    }\n}\n")
    assert not parsed.ok
    assert all(issue.range.start.line == 3 for issue in parsed.issues)


def test_missing_token_is_reported():
    parsed = parse("class A { void f() { int x = 1 } }")
    assert not parsed.ok
    assert any(i.kind == "missing" for i in parsed.issues)


def test_cyrillic_ranges_are_utf16_columns():
    src = 'class A {\n    String s = "Привет, мир"; // комментарий\n}\n'
    parsed = parse(src)
    assert parsed.ok
    literal = find_all(parsed, "string_literal")[0]
    rng = parsed.range_of(literal)
    # 4 пробела + "String s = " (11 символов) → литерал начинается с колонки 16 (1-based)
    assert rng.start == Position(2, 16)
    # "Привет, мир" = 11 символов + 2 кавычки → конец на колонке 16 + 13 = 29
    assert rng.end == Position(2, 29)
    # в байтах литерал длиннее: 9 кириллических букв занимают по 2 байта
    assert literal.end_byte - literal.start_byte == 13 + 9


def test_emoji_counts_as_two_utf16_units():
    src = 'class A { String s = "😀x"; int y; }'
    parsed = parse(src)
    assert parsed.ok
    field = find_all(parsed, "field_declaration")[1]
    # 😀 занимает 2 единицы UTF-16 (и 1 символ Python): колонка = индекс + 1 (суррогатная пара) + 1
    expected_col = src.index("int y") + 1 + 1
    assert parsed.range_of(field).start == Position(1, expected_col)


def test_crlf_and_tabs():
    src = "class A {\r\n\tint x;\r\n\tint y;\r\n}\r\n"
    parsed = parse(src)
    assert parsed.ok
    fields = find_all(parsed, "field_declaration")
    starts = sorted(parsed.range_of(f).start for f in fields)
    assert starts == [Position(2, 2), Position(3, 2)]  # табуляция — одна колонка


def test_offset_roundtrip_with_cyrillic_and_emoji():
    src = "class A {\n    // Привет 😀 мир\n    int x;\n}\n"
    parsed = parse(src)
    checked = 0
    for offset in range(len(parsed.source) + 1):
        try:
            parsed.source[:offset].decode("utf-8")
        except UnicodeDecodeError:
            continue  # середина многобайтового символа
        pos = parsed.lines.position(offset)
        assert parsed.lines.offset(pos) == offset
        checked += 1
    assert checked > 30


def test_query_api_available():
    from tree_sitter import Query, QueryCursor

    parsed = parse("class A { void f() {} void g() {} }")
    query = Query(JAVA_LANGUAGE, "(method_declaration name: (identifier) @name)")
    captures = QueryCursor(query).captures(parsed.root)
    names = sorted(parsed.text(n) for n in captures["name"])
    assert names == ["f", "g"]
