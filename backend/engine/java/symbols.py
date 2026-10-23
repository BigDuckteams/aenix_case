"""Декларации Java-файла: пакет, импорты, типы и их члены (S2.2).

Модель неизменяемая и не хранит узлы tree-sitter: только имена, текст типов и байтовые диапазоны.
Узел объявления при необходимости находится заново по диапазону (``cst.find_node``).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from tree_sitter import Node

from engine.graph import ids
from engine.java import cst
from engine.java.ts import ParsedFile

_GENERICS = re.compile(r"<.*>", re.DOTALL)


def base_name(type_text: str) -> str:
    """Простое имя типа без дженериков, массивов и пакета: ``java.util.List<A>[]`` → ``List``."""
    text = _GENERICS.sub("", type_text).replace("[]", "").replace("...", "").strip()
    return text.rsplit(".", 1)[-1]


@dataclass(frozen=True, slots=True)
class Param:
    name: str
    type: str
    varargs: bool = False


@dataclass(frozen=True, slots=True)
class Member:
    id: str
    kind: str  # field | constructor | method | initializer
    role: str  # field | constant | component | constructor | compact_constructor | method | init | static_init
    name: str
    key: str
    type_path: str
    type_text: str | None  # тип поля или возвращаемый тип
    params: tuple[Param, ...]
    modifiers: tuple[str, ...]
    annotations: tuple[str, ...]
    throws: tuple[str, ...]
    type_params: tuple[str, ...]
    start_byte: int
    end_byte: int
    decl_type: str  # тип узла CST, по нему объявление находится заново
    has_body: bool

    @property
    def is_static(self) -> bool:
        return "static" in self.modifiers or self.role in {"static_init", "constant"}

    @property
    def signature(self) -> str:
        return self.key


@dataclass(frozen=True, slots=True)
class TypeDecl:
    id: str
    kind: str  # class | interface | enum | record | annotation
    name: str
    path: str  # Outer.Inner
    parent_path: str | None
    modifiers: tuple[str, ...]
    annotations: tuple[str, ...]
    type_params: tuple[str, ...]
    extends: tuple[str, ...]  # у класса — суперкласс, у интерфейса — расширяемые интерфейсы
    implements: tuple[str, ...]
    permits: tuple[str, ...]
    components: tuple[Param, ...]  # компоненты record
    constants: tuple[str, ...]  # константы enum
    members: tuple[Member, ...]
    nested: tuple[TypeDecl, ...]
    start_byte: int
    end_byte: int
    decl_type: str

    def iter_types(self) -> Iterator[TypeDecl]:
        yield self
        for inner in self.nested:
            yield from inner.iter_types()


@dataclass(frozen=True, slots=True)
class FileSymbols:
    file: str
    package: str | None
    imports: tuple[str, ...]
    types: tuple[TypeDecl, ...]
    main_classes: tuple[str, ...] = field(default=())

    def all_types(self) -> Iterator[TypeDecl]:
        for top in self.types:
            yield from top.iter_types()

    def all_members(self) -> Iterator[Member]:
        for decl in self.all_types():
            yield from decl.members


# --- извлечение ----------------------------------------------------------------------------------

_BODY_TYPES = {
    "class_declaration": "class",
    "interface_declaration": "interface",
    "enum_declaration": "enum",
    "record_declaration": "record",
    "annotation_type_declaration": "annotation",
}


def extract_symbols(parsed: ParsedFile, file: str) -> FileSymbols:
    package: str | None = None
    imports: list[str] = []
    types: list[TypeDecl] = []
    for child in parsed.root.children:
        if child.type == "package_declaration":
            package = _qualified_name(parsed, child)
        elif child.type == "import_declaration":
            imports.append(
                cst.squash(parsed.text(child)).removeprefix("import ").rstrip(";").strip()
            )
        elif child.type in cst.TYPE_DECLARATIONS:
            types.append(_type_decl(parsed, file, child, None))
    mains: list[str] = []
    for decl in (d for t in types for d in t.iter_types()):
        for member in decl.members:
            if _is_main(member):
                qualified = f"{package}.{decl.path}" if package else decl.path
                mains.append(qualified)
    return FileSymbols(file, package, tuple(imports), tuple(types), tuple(mains))


def _is_main(member: Member) -> bool:
    return (
        member.kind == "method"
        and member.name == "main"
        and {"public", "static"} <= set(member.modifiers)
        and member.type_text == "void"
        and len(member.params) == 1
        and base_name(member.params[0].type) == "String"
    )


def _qualified_name(parsed: ParsedFile, node: Node) -> str:
    for child in node.children:
        if child.type in {"scoped_identifier", "identifier"}:
            return parsed.text(child)
    return ""


def _type_list(parsed: ParsedFile, node: Node | None) -> tuple[str, ...]:
    if node is None:
        return ()
    items: list[str] = []
    for child in node.children:
        if child.type == "type_list":
            items.extend(cst.squash(parsed.text(t)) for t in cst.named_children(child))
        elif child.is_named and child.type not in cst.COMMENT_TYPES:
            items.append(cst.squash(parsed.text(child)))
    return tuple(items)


def _type_params(parsed: ParsedFile, node: Node) -> tuple[str, ...]:
    holder = node.child_by_field_name("type_parameters")
    if holder is None:
        return ()
    return tuple(cst.squash(parsed.text(p)) for p in holder.children if p.type == "type_parameter")


def _dims(parsed: ParsedFile, node: Node) -> str:
    dims = cst.first_child_of_type(node, "dimensions")
    return "" if dims is None else cst.squash(parsed.text(dims)).replace(" ", "")


def _params(parsed: ParsedFile, formal: Node | None) -> tuple[Param, ...]:
    if formal is None:
        return ()
    params: list[Param] = []
    for child in formal.children:
        if child.type == "formal_parameter":
            type_node = child.child_by_field_name("type")
            name = child.child_by_field_name("name")
            params.append(
                Param(
                    cst.text_of(parsed, name),
                    cst.squash(cst.text_of(parsed, type_node)) + _dims(parsed, child),
                )
            )
        elif child.type == "spread_parameter":
            declarator = cst.first_child_of_type(child, "variable_declarator")
            name = declarator.child_by_field_name("name") if declarator is not None else None
            type_node = next(
                (
                    c
                    for c in child.children
                    if c.is_named and c.type not in {"modifiers", "variable_declarator"}
                ),
                None,
            )
            params.append(
                Param(
                    cst.text_of(parsed, name),
                    cst.squash(cst.text_of(parsed, type_node)) + "...",
                    True,
                )
            )
    return tuple(params)


def _member_key(name: str, params: tuple[Param, ...]) -> str:
    return f"{name}({', '.join(p.type for p in params)})"


def _body_of(node: Node) -> Node | None:
    return node.child_by_field_name("body")


def _type_decl(parsed: ParsedFile, file: str, node: Node, parent_path: str | None) -> TypeDecl:
    name = cst.text_of(parsed, node.child_by_field_name("name"))
    path = f"{parent_path}.{name}" if parent_path else name
    kind = _BODY_TYPES[node.type]
    mods, annotations = cst.modifiers_of(parsed, node)

    extends: tuple[str, ...] = ()
    implements: tuple[str, ...] = ()
    permits: tuple[str, ...] = ()
    for child in node.children:
        if child.type in {"superclass", "extends_interfaces"}:
            extends = _type_list(parsed, child)
        elif child.type == "super_interfaces":
            implements = _type_list(parsed, child)
        elif child.type == "permits":
            permits = _type_list(parsed, child)

    components: tuple[Param, ...] = ()
    constants: list[str] = []
    members: list[Member] = []
    nested: list[TypeDecl] = []

    if kind == "record":
        components = _params(parsed, node.child_by_field_name("parameters"))
        for component in components:
            members.append(
                _synthetic_field(file, path, component.name, component.type, "component", node)
            )

    body = _body_of(node)
    if body is not None:
        init_counts = {"init": 0, "static_init": 0}
        for member_node in _body_members(body):
            _collect_member(
                parsed, file, path, member_node, members, nested, constants, init_counts, kind
            )

    return TypeDecl(
        id=ids.type_id(file, path),
        kind=kind,
        name=name,
        path=path,
        parent_path=parent_path,
        modifiers=mods,
        annotations=annotations,
        type_params=_type_params(parsed, node),
        extends=extends,
        implements=implements,
        permits=permits,
        components=components,
        constants=tuple(constants),
        members=tuple(members),
        nested=tuple(nested),
        start_byte=node.start_byte,
        end_byte=node.end_byte,
        decl_type=node.type,
    )


def _body_members(body: Node) -> list[Node]:
    items: list[Node] = []
    for child in cst.named_children(body):
        if child.type == "enum_body_declarations":
            items.extend(cst.named_children(child))
        else:
            items.append(child)
    return items


def _synthetic_field(
    file: str, type_path: str, name: str, type_text: str, role: str, node: Node
) -> Member:
    return Member(
        id=ids.member_id(file, type_path, name),
        kind="field",
        role=role,
        name=name,
        key=name,
        type_path=type_path,
        type_text=type_text,
        params=(),
        modifiers=("private", "final") if role == "component" else ("public", "static", "final"),
        annotations=(),
        throws=(),
        type_params=(),
        start_byte=node.start_byte,
        end_byte=node.end_byte,
        decl_type=node.type,
        has_body=False,
    )


def _collect_member(
    parsed: ParsedFile,
    file: str,
    type_path: str,
    node: Node,
    members: list[Member],
    nested: list[TypeDecl],
    constants: list[str],
    init_counts: dict[str, int],
    owner_kind: str,
) -> None:
    kind = node.type
    if kind in cst.TYPE_DECLARATIONS:
        nested.append(_type_decl(parsed, file, node, type_path))
    elif kind == "enum_constant":
        name = cst.text_of(parsed, node.child_by_field_name("name"))
        constants.append(name)
        members.append(_synthetic_field(file, type_path, name, type_path, "constant", node))
    elif kind in {"field_declaration", "constant_declaration"}:
        mods, annotations = cst.modifiers_of(parsed, node)
        if owner_kind == "interface":
            mods = (*mods, "static", "final")
        type_text = cst.squash(cst.text_of(parsed, node.child_by_field_name("type")))
        for declarator in cst.children_of_type(node, "variable_declarator"):
            name = cst.text_of(parsed, declarator.child_by_field_name("name"))
            members.append(
                Member(
                    id=ids.member_id(file, type_path, name),
                    kind="field",
                    role="field",
                    name=name,
                    key=name,
                    type_path=type_path,
                    type_text=type_text + _dims(parsed, declarator),
                    params=(),
                    modifiers=mods,
                    annotations=annotations,
                    throws=(),
                    type_params=(),
                    start_byte=node.start_byte,
                    end_byte=node.end_byte,
                    decl_type=node.type,
                    has_body=False,
                )
            )
    elif kind in {
        "method_declaration",
        "constructor_declaration",
        "compact_constructor_declaration",
    }:
        mods, annotations = cst.modifiers_of(parsed, node)
        name = cst.text_of(parsed, node.child_by_field_name("name"))
        if kind == "compact_constructor_declaration":
            params = tuple(_record_components(members))
        else:
            params = _params(parsed, node.child_by_field_name("parameters"))
        throws_node = cst.first_child_of_type(node, "throws")
        key = _member_key(name, params)
        is_method = kind == "method_declaration"
        if is_method and owner_kind == "interface":
            body_present = _body_of(node) is not None
            if not body_present:
                mods = (*mods, "abstract")
            if not {"private", "public"} & set(mods):
                mods = (*mods, "public")
        members.append(
            Member(
                id=ids.member_id(file, type_path, key),
                kind="method" if is_method else "constructor",
                role="method"
                if is_method
                else ("compact_constructor" if kind.startswith("compact") else "constructor"),
                name=name,
                key=key,
                type_path=type_path,
                type_text=cst.squash(cst.text_of(parsed, node.child_by_field_name("type")))
                if is_method
                else None,
                params=params,
                modifiers=mods,
                annotations=annotations,
                throws=_type_list(parsed, throws_node),
                type_params=_type_params(parsed, node),
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                decl_type=node.type,
                has_body=_body_of(node) is not None,
            )
        )
    elif kind in {"static_initializer", "block"}:
        role = "static_init" if kind == "static_initializer" else "init"
        index = init_counts[role]
        init_counts[role] += 1
        key = f"<{'clinit' if role == 'static_init' else 'init'}>[{index}]"
        members.append(
            Member(
                id=ids.member_id(file, type_path, key),
                kind="initializer",
                role=role,
                name=key,
                key=key,
                type_path=type_path,
                type_text=None,
                params=(),
                modifiers=("static",) if role == "static_init" else (),
                annotations=(),
                throws=(),
                type_params=(),
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                decl_type=node.type,
                has_body=True,
            )
        )


def _record_components(members: list[Member]) -> list[Param]:
    return [Param(m.name, m.type_text or "") for m in members if m.role == "component"]
