"""Лёгкая семантика: таблица типов проекта, объявленные типы переменных, разрешение вызовов.

Сделано то, что нужно графу (бейджи ``call``, рёбра ``calls``/``uses``):

* таблица типов проекта и их иерархия (``extends``/``implements``, подтипы, внешние типы);
* **объявленные** типы локальных переменных и параметров (плоская область видимости метода: при
  одинаковых именах в соседних блоках побеждает последнее объявление);
* тип выражения для простых случаев (имя, ``this``, ``new T()``, поле, вызов метода проекта,
  приведение, литералы, строковая конкатенация);
* разрешение вызова методов и конструкторов проекта по имени, арности и типу получателя; через
  интерфейс и абстрактный метод возвращаются все реализации; при неизвестном получателе вызов не
  разрешается (консервативно: лучше без ребра, чем с ложным).

Вывод типов JDK (каталог ``String``/``List``/``Stream``…), эффекты и чистота методов — задачи S2.3
и S2.4, они поверх этой основы.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from tree_sitter import Node

from engine.java import cst
from engine.java.symbols import FileSymbols, Member, TypeDecl, base_name
from engine.java.ts import ParsedFile

_LITERAL_TYPES = {
    "decimal_integer_literal": "int",
    "hex_integer_literal": "int",
    "binary_integer_literal": "int",
    "octal_integer_literal": "int",
    "decimal_floating_point_literal": "double",
    "hex_floating_point_literal": "double",
    "string_literal": "String",
    "character_literal": "char",
    "true": "boolean",
    "false": "boolean",
}


class SymbolTable:
    """Все типы проекта и операции над их иерархией."""

    def __init__(self, files: Iterable[FileSymbols]) -> None:
        self.by_name: dict[str, list[TypeDecl]] = {}
        self.by_id: dict[str, TypeDecl] = {}
        self.owner_of: dict[str, TypeDecl] = {}  # id члена → тип-владелец
        self.members: dict[str, Member] = {}
        for symbols in files:
            for decl in symbols.all_types():
                self.by_name.setdefault(decl.name, []).append(decl)
                self.by_id[decl.id] = decl
                for member in decl.members:
                    self.owner_of[member.id] = decl
                    self.members[member.id] = member
        self._supers: dict[str, list[TypeDecl]] = {}
        self._subs: dict[str, list[TypeDecl]] = {}
        self._build_hierarchy()

    # --- иерархия --------------------------------------------------------------------------

    def type_named(self, name: str, near: TypeDecl | None = None) -> TypeDecl | None:
        candidates = self.by_name.get(base_name(name), [])
        if not candidates:
            return None
        if near is not None:
            file = near.id.split("#", 1)[0]
            for decl in candidates:
                if decl.id.startswith(file + "#"):
                    return decl
        return candidates[0]

    def direct_supers(self, decl: TypeDecl) -> list[TypeDecl]:
        found: list[TypeDecl] = []
        for text in (*decl.extends, *decl.implements):
            parent = self.type_named(text, decl)
            if parent is not None and parent.id != decl.id:
                found.append(parent)
        return found

    def _build_hierarchy(self) -> None:
        for decl in self.by_id.values():
            seen: dict[str, TypeDecl] = {}
            stack = self.direct_supers(decl)
            while stack:
                parent = stack.pop(0)
                if parent.id in seen or parent.id == decl.id:
                    continue
                seen[parent.id] = parent
                stack.extend(self.direct_supers(parent))
            self._supers[decl.id] = list(seen.values())
            for parent in seen.values():
                self._subs.setdefault(parent.id, []).append(decl)

    def supertypes(self, decl: TypeDecl) -> list[TypeDecl]:
        return self._supers.get(decl.id, [])

    def subtypes(self, decl: TypeDecl) -> list[TypeDecl]:
        return self._subs.get(decl.id, [])

    def outer(self, decl: TypeDecl) -> TypeDecl | None:
        if decl.parent_path is None:
            return None
        file = decl.id.split("#", 1)[0]
        return self.by_id.get(f"{file}#{decl.parent_path}")

    # --- поиск членов ----------------------------------------------------------------------

    def methods_named(self, decl: TypeDecl, name: str, arity: int) -> list[Member]:
        return [m for m in decl.members if m.kind == "method" and m.name == name and fits(m, arity)]

    def find_methods(self, decl: TypeDecl, name: str, arity: int) -> list[Member]:
        """Методы с таким именем в типе и его надтипах; сами подтипы — в ``with_overrides``."""
        found = self.methods_named(decl, name, arity)
        if found:
            return found
        for parent in self.supertypes(decl):
            found = self.methods_named(parent, name, arity)
            if found:
                return found
        return []

    def with_overrides(self, decl: TypeDecl, methods: list[Member]) -> list[Member]:
        """Добавляет переопределения в подтипах: вызов через интерфейс — все реализации."""
        result = list(methods)
        known = {m.id for m in result}
        for method in methods:
            for sub in self.subtypes(decl):
                for override in self.methods_named(sub, method.name, len(method.params)):
                    if override.id not in known:
                        known.add(override.id)
                        result.append(override)
        return result

    def constructors(self, decl: TypeDecl, arity: int) -> list[Member]:
        return [m for m in decl.members if m.kind == "constructor" and fits(m, arity)]

    def field_type(self, decl: TypeDecl, name: str) -> tuple[Member, TypeDecl] | None:
        """Поле в типе, его надтипах и внешних типах (по порядку видимости)."""
        scope: TypeDecl | None = decl
        while scope is not None:
            for candidate in (scope, *self.supertypes(scope)):
                for member in candidate.members:
                    if member.kind == "field" and member.name == name:
                        return member, candidate
            scope = self.outer(scope)
        return None


def fits(member: Member, arity: int) -> bool:
    if member.params and member.params[-1].varargs:
        return arity >= len(member.params) - 1
    return len(member.params) == arity


# --- область видимости метода ----------------------------------------------------------------


def declared_types(
    parsed: ParsedFile, body: Node, params: Iterable[tuple[str, str]]
) -> dict[str, str]:
    """Имя → объявленный тип для параметров и локальных переменных (``var`` → тип по инициализатору)."""
    scope: dict[str, str] = {name: type_text for name, type_text in params}
    for node in cst.walk(body):
        kind = node.type
        if kind == "local_variable_declaration":
            type_text = cst.text_of(parsed, node.child_by_field_name("type"))
            for declarator in cst.children_of_type(node, "variable_declarator"):
                name = cst.text_of(parsed, declarator.child_by_field_name("name"))
                scope[name] = _declared(parsed, type_text, declarator.child_by_field_name("value"))
        elif kind == "enhanced_for_statement":
            type_text = cst.text_of(parsed, node.child_by_field_name("type"))
            name = cst.text_of(parsed, node.child_by_field_name("name"))
            scope[name] = "" if type_text == "var" else type_text
        elif kind == "catch_formal_parameter":
            catch_type = cst.first_child_of_type(node, "catch_type")
            first = cst.named_children(catch_type)[0] if catch_type is not None else None
            name = cst.text_of(parsed, node.child_by_field_name("name"))
            scope[name] = cst.text_of(parsed, first)
        elif kind == "resource":
            name = cst.text_of(parsed, node.child_by_field_name("name"))
            type_text = cst.text_of(parsed, node.child_by_field_name("type"))
            scope[name] = _declared(parsed, type_text, node.child_by_field_name("value"))
        elif kind == "lambda_expression":
            holder = node.child_by_field_name("parameters")
            if holder is not None:
                if holder.type == "identifier":
                    scope.setdefault(parsed.text(holder), "")
                else:
                    for item in cst.walk(holder):
                        if item.type == "identifier":
                            scope.setdefault(parsed.text(item), "")
                        elif item.type == "formal_parameter":
                            name = cst.text_of(parsed, item.child_by_field_name("name"))
                            scope[name] = cst.text_of(parsed, item.child_by_field_name("type"))
    return scope


def _declared(parsed: ParsedFile, type_text: str, value: Node | None) -> str:
    if type_text != "var":
        return type_text
    if value is not None and value.type == "object_creation_expression":
        return cst.text_of(parsed, value.child_by_field_name("type"))
    return ""


# --- тип выражения и разрешение вызовов -------------------------------------------------------


@dataclass(slots=True)
class Context:
    parsed: ParsedFile
    table: SymbolTable
    owner: TypeDecl
    scope: dict[str, str] = field(default_factory=dict)

    def argument_count(self, call: Node) -> int:
        arguments = call.child_by_field_name("arguments")
        return 0 if arguments is None else len(cst.named_children(arguments))

    def expr_type(self, node: Node | None, depth: int = 0) -> str | None:
        """Простое имя типа выражения или ``None``, если вывести не удалось."""
        if node is None or depth > 6:
            return None
        kind = node.type
        if kind in _LITERAL_TYPES:
            return _LITERAL_TYPES[kind]
        if kind == "parenthesized_expression":
            inner = cst.named_children(node)
            return self.expr_type(inner[0], depth + 1) if inner else None
        if kind == "this":
            return self.owner.name
        if kind == "identifier":
            name = self.parsed.text(node)
            if name in self.scope:
                return base_name(self.scope[name]) or None
            found = self.table.field_type(self.owner, name)
            if found is not None:
                return base_name(found[0].type_text or "") or None
            return None
        if kind == "object_creation_expression":
            return base_name(cst.text_of(self.parsed, node.child_by_field_name("type"))) or None
        if kind == "cast_expression":
            return base_name(cst.text_of(self.parsed, node.child_by_field_name("type"))) or None
        if kind == "field_access":
            target = node.child_by_field_name("object")
            name = cst.text_of(self.parsed, node.child_by_field_name("field"))
            if name == "length" and self._is_array(target):
                return "int"
            decl = self._decl_for(target, depth)
            if decl is not None:
                found = self.table.field_type(decl, name)
                if found is not None:
                    return base_name(found[0].type_text or "") or None
            return None
        if kind == "array_access":
            return self._element_type(node.child_by_field_name("array"), depth)
        if kind == "method_invocation":
            return self._call_return_type(node, depth)
        if kind == "binary_expression":
            operator = cst.text_of(self.parsed, node.child_by_field_name("operator"))
            left = self.expr_type(node.child_by_field_name("left"), depth + 1)
            right = self.expr_type(node.child_by_field_name("right"), depth + 1)
            if operator == "+" and "String" in (left, right):
                return "String"
            if operator in {"==", "!=", "<", ">", "<=", ">=", "&&", "||"}:
                return "boolean"
        return None

    def _is_array(self, node: Node | None) -> bool:
        if node is None or node.type != "identifier":
            return False
        return "[" in self.scope.get(self.parsed.text(node), "")

    def _element_type(self, node: Node | None, depth: int) -> str | None:
        if node is None or node.type != "identifier":
            return None
        declared = self.scope.get(self.parsed.text(node), "")
        return base_name(declared) if "[" in declared else None

    def _decl_for(self, node: Node | None, depth: int) -> TypeDecl | None:
        name = self.expr_type(node, depth + 1)
        return self.table.type_named(name, self.owner) if name else None

    def _call_return_type(self, call: Node, depth: int) -> str | None:
        targets = self.resolve_call(call, depth + 1)
        returns = {base_name(m.type_text or "") for m in targets if m.type_text}
        return returns.pop() if len(returns) == 1 else None

    def resolve_call(self, call: Node, depth: int = 0) -> list[Member]:
        """Методы проекта, которые может вызывать ``method_invocation`` (пусто — внешний вызов)."""
        name = cst.text_of(self.parsed, call.child_by_field_name("name"))
        arity = self.argument_count(call)
        target = call.child_by_field_name("object")
        table = self.table

        if target is None or target.type == "this":
            return self._unqualified(name, arity)
        if target.type == "super":
            found: list[Member] = []
            for parent in table.supertypes(self.owner):
                found = table.methods_named(parent, name, arity)
                if found:
                    break
            return found

        decl: TypeDecl | None = None
        static_only = False
        if target.type == "identifier":
            ident = self.parsed.text(target)
            if ident in self.scope or table.field_type(self.owner, ident) is not None:
                decl = self._decl_for(target, depth)
            else:
                decl = table.type_named(ident, self.owner)
                static_only = decl is not None
        else:
            decl = self._decl_for(target, depth)
        if decl is None:
            return []
        methods = table.find_methods(decl, name, arity)
        if static_only:
            methods = [m for m in methods if m.is_static]
        return table.with_overrides(decl, methods)

    def _unqualified(self, name: str, arity: int) -> list[Member]:
        table = self.table
        scope: TypeDecl | None = self.owner
        while scope is not None:
            methods = table.find_methods(scope, name, arity)
            if methods:
                return table.with_overrides(scope, methods)
            scope = table.outer(scope)
        return []

    def resolve_creation(self, creation: Node) -> list[Member]:
        """Конструкторы проекта для ``new T(...)`` (пусто для внешних типов и типов без конструктора)."""
        type_node = creation.child_by_field_name("type")
        decl = self.table.type_named(cst.text_of(self.parsed, type_node), self.owner)
        if decl is None:
            return []
        return self.table.constructors(decl, self.argument_count(creation))

    def resolve_explicit_constructor(self, node: Node) -> list[Member]:
        """``this(...)`` и ``super(...)`` в конструкторе."""
        target = node.child_by_field_name("constructor")
        arity = self.argument_count(node)
        if target is not None and target.type == "this":
            return self.table.constructors(self.owner, arity)
        for parent in self.table.direct_supers(self.owner):
            found = self.table.constructors(parent, arity)
            if found:
                return found
        return []
