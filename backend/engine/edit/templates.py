"""Шаблоны блоков палитры и проверка полей формы (S5.3, docs/04 § 5.4)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from engine.edit.core import check_fragment, invalid, unsupported

ASSIGN_OPS = ("=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=", "++", "--")
INSERTABLE = (
    "var_decl",
    "assign",
    "operation",
    "condition",
    "loop_for",
    "loop_foreach",
    "loop_while",
    "try",
    "throw",
    "return",
    "break",
    "continue",
    "code",
)
_FOR_PART = re.compile(r"^[^;{}]*$")


def text_field(fields: Mapping[str, Any], name: str, *, required: bool = True) -> str:
    value = fields.get(name)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise invalid("поле обязательно", name)
        return ""
    return str(value).strip()


def expression(fields: Mapping[str, Any], name: str, *, required: bool = True) -> str:
    value = text_field(fields, name, required=required)
    return check_fragment("expression", value, name) if value else ""


def type_name(fields: Mapping[str, Any], name: str, default: str | None = None) -> str:
    value = text_field(fields, name, required=default is None) or (default or "")
    return check_fragment("type", value, name)


def identifier(fields: Mapping[str, Any], name: str, default: str | None = None) -> str:
    value = text_field(fields, name, required=default is None) or (default or "")
    return check_fragment("identifier", value, name)


def label(fields: Mapping[str, Any]) -> str:
    value = text_field(fields, "label", required=False)
    return check_fragment("identifier", value, "label") if value else ""


def for_header(fields: Mapping[str, Any], current: Mapping[str, str] | None = None) -> str:
    """``init; cond; update`` — части без значения берутся из ``current``."""
    parts = []
    for name in ("init", "cond", "update"):
        raw = fields.get(name)
        text = str(raw).strip() if raw is not None else (current or {}).get(name, "")
        if text and not _FOR_PART.match(text):
            raise invalid("часть заголовка не должна содержать «;» или скобки блока", name)
        if text and name == "cond":
            check_fragment("expression", text, name)
        if text and name == "update":
            for piece in text.split(","):
                check_fragment("expression", piece, name)
        parts.append(text)
    return "; ".join(parts).rstrip()


def assign_text(fields: Mapping[str, Any]) -> str:
    target = expression(fields, "target")
    op = str(fields.get("op") or "=")
    if op not in ASSIGN_OPS:
        raise invalid(f"неизвестный оператор «{op}»", "op")
    if op in {"++", "--"}:
        return f"{target}{op};"
    return f"{target} {op} {expression(fields, 'value')};"


def var_text(fields: Mapping[str, Any], modifiers: list[str] | None = None) -> str:
    prefix = " ".join(modifiers or [])
    head = f"{prefix} " if prefix else ""
    declared = f"{head}{type_name(fields, 'type')} {identifier(fields, 'name')}"
    value = expression(fields, "value", required=False)
    return f"{declared} = {value};" if value else f"{declared};"


def render(kind: str, fields: Mapping[str, Any], unit: str) -> str:
    """Текст оператора вида ``kind`` без отступа первой строки (тела — на уровне ``unit``)."""
    if kind == "var_decl":
        return var_text(fields)
    if kind == "assign":
        return assign_text(fields)
    if kind == "operation":
        return f"{expression(fields, 'expr')};"
    if kind == "return":
        value = expression(fields, "expr", required=False)
        return f"return {value};" if value else "return;"
    if kind == "throw":
        return f"throw {expression(fields, 'expr')};"
    if kind in {"break", "continue"}:
        name = label(fields)
        return f"{kind} {name};" if name else f"{kind};"
    if kind == "condition":
        text = f"if ({expression(fields, 'expr')}) {{\n}}"
        return text + " else {\n}" if fields.get("add_else") else text
    if kind == "loop_for":
        return f"for ({for_header(fields)}) {{\n}}"
    if kind == "loop_foreach":
        header = f"{type_name(fields, 'type')} {identifier(fields, 'name')} : {expression(fields, 'iterable')}"
        return f"for ({header}) {{\n}}"
    if kind == "loop_while":
        cond = expression(fields, "cond")
        return f"do {{\n}} while ({cond});" if fields.get("do_while") else f"while ({cond}) {{\n}}"
    if kind == "try":
        exc = type_name(fields, "exception_type", "Exception")
        name = identifier(fields, "name", "e")
        text = f"try {{\n}} catch ({exc} {name}) {{\n}}"
        return text + " finally {\n}" if fields.get("add_finally") else text
    if kind == "code":
        code = text_field(fields, "text")
        return code
    raise unsupported(f"блок «{kind}» нельзя вставить из палитры")
