"""Операции над графом через API: пакет → версия ``graph_op`` (S5.8, docs/08 § 5)."""

from __future__ import annotations

from sqlmodel import Session

from app.db.models import Project, VersionOrigin
from app.errors import ApiError, not_found
from app.schemas import ops as schemas
from app.schemas.project import VersionInfo
from app.services import graphs
from app.services import versions as versions_service
from engine.edit.core import EditError, check_fragment
from engine.edit.pipeline import apply_ops
from engine.graph.ids import split_node_id
from engine.java.project import get_project

_STATUS = {
    "INVALID_FRAGMENT": 422,
    "PRECONDITION_FAILED": 422,
    "UNSUPPORTED": 422,
    "NOT_FOUND": 404,
}


def _raw(payload: schemas.OpsRequest) -> list[dict[str, object]]:
    return [op.model_dump(mode="python") for op in payload.ops]


def api_error(error: EditError) -> ApiError:
    details: dict[str, object] = {"op_index": error.op_index}
    for key in ("field", "line", "column"):
        value = getattr(error, key)
        if value is not None:
            details[key] = value
    return ApiError(_STATUS.get(error.code, 422), error.code, error.message, details)


def describe(payload: schemas.OpsRequest) -> str:
    if payload.description:
        return payload.description
    names = [op.op for op in payload.ops]
    shown = ", ".join(dict.fromkeys(names))
    return f"Граф: {shown}" if len(names) == 1 else f"Граф ({len(names)} операций): {shown}"


def apply(session: Session, project: Project, payload: schemas.OpsRequest) -> schemas.OpsResult:
    versions_service.require_head(project, payload.base_version_id)
    head = versions_service.head_version(session, project)
    files = versions_service.version_files(session, head.id or 0)
    try:
        result = apply_ops(files, _raw(payload))  # type: ignore[arg-type]
    except EditError as error:
        raise api_error(error) from error

    if result.files == files:
        version = head
    else:
        version = versions_service.create_version(
            session,
            project,
            result.files,
            origin=VersionOrigin.GRAPH_OP,
            description=describe(payload),
            parent_id=head.id,
        )
    java = get_project(result.files)
    flow = None
    if result.focus_node_id:
        method_id = split_node_id(result.focus_node_id)[0]
        if java.flow(method_id) is not None:
            flow = graphs.flow_schema(java, version, method_id)
    return schemas.OpsResult(
        version=versions_service.version_info(version),
        changed_files=result.changed,
        focus_node_id=result.focus_node_id,
        id_map=result.id_map,
        flow=flow,
        syntax_errors=versions_service.syntax_issues(java, set(result.changed)),
    )


def validate(
    session: Session, project: Project, payload: schemas.OpsRequest
) -> schemas.OpsValidation:
    head = versions_service.head_version(session, project)
    files = versions_service.version_files(session, head.id or 0)
    try:
        result = apply_ops(files, _raw(payload))  # type: ignore[arg-type]
    except EditError as error:
        return schemas.OpsValidation(
            ok=False,
            errors=[
                schemas.OpError(
                    op_index=error.op_index,
                    code=error.code,  # type: ignore[arg-type]
                    message=error.message,
                    field=error.field,
                    line=error.line,
                    column=error.column,
                )
            ],
            diff=[],
        )
    old = {p: files[p] for p in result.changed if p in files}
    new = {p: result.files[p] for p in result.changed if p in result.files}
    return schemas.OpsValidation(ok=True, errors=[], diff=versions_service.diff_files(old, new))


def check_expression(
    session: Session, project: Project, payload: schemas.ExpressionCheck
) -> schemas.ExpressionResult:
    text = payload.text
    try:
        check_fragment(payload.kind, text, "text")
    except EditError as error:
        return schemas.ExpressionResult(
            ok=False, error=schemas.ExpressionIssue(message=error.message)
        )
    if payload.kind == "identifier" and payload.context_node_id:
        head = versions_service.head_version(session, project)
        java = get_project(versions_service.version_files(session, head.id or 0))
        member = java.member(split_node_id(payload.context_node_id)[0])
        if member is None:
            raise not_found(f"узел {payload.context_node_id} не найден")
        if text.strip() in java.context(member)[0].scope:
            return schemas.ExpressionResult(
                ok=False,
                error=schemas.ExpressionIssue(message=f"имя «{text.strip()}» уже занято в методе"),
            )
    return schemas.ExpressionResult(ok=True)


def _field(
    name: str,
    label: str,
    type_: str,
    *,
    required: bool = True,
    default: str | bool | None = None,
    options: list[str] | None = None,
) -> schemas.PaletteField:
    return schemas.PaletteField(
        name=name,
        label=label,
        type=type_,  # type: ignore[arg-type]
        required=required,
        default=default,
        options=options or [],
    )


def palette() -> schemas.Palette:
    ops = ["=", "+=", "-=", "*=", "/=", "%=", "++", "--"]
    blocks = [
        (
            "var_decl",
            "Переменная",
            "basic",
            "violet",
            "box",
            "int count = 0;",
            [
                _field("type", "Тип", "type", default="int"),
                _field("name", "Имя", "identifier"),
                _field("value", "Значение", "expression", required=False),
            ],
        ),
        (
            "assign",
            "Присваивание",
            "basic",
            "blue",
            "equal",
            "total += price;",
            [
                _field("target", "Цель", "expression"),
                _field("op", "Оператор", "select", default="=", options=ops),
                _field("value", "Значение", "expression", required=False),
            ],
        ),
        (
            "operation",
            "Операция",
            "basic",
            "teal",
            "terminal",
            'System.out.println("…");',
            [_field("expr", "Выражение", "expression")],
        ),
        (
            "return",
            "Возврат",
            "basic",
            "green",
            "corner-down-left",
            "return result;",
            [_field("expr", "Значение", "expression", required=False)],
        ),
        (
            "condition",
            "Условие",
            "control",
            "orange",
            "git-branch",
            "if (cond) { }",
            [
                _field("expr", "Условие", "expression"),
                _field("add_else", "Добавить else", "boolean", required=False, default=False),
            ],
        ),
        (
            "loop_for",
            "Цикл for",
            "control",
            "orange",
            "repeat",
            "for (int i = 0; i < n; i++) { }",
            [
                _field("init", "Инициализация", "text", default="int i = 0"),
                _field("cond", "Условие", "expression", default="i < n"),
                _field("update", "Шаг", "text", default="i++"),
            ],
        ),
        (
            "loop_foreach",
            "Цикл for each",
            "control",
            "orange",
            "repeat",
            "for (Order o : orders) { }",
            [
                _field("type", "Тип", "type"),
                _field("name", "Имя", "identifier"),
                _field("iterable", "Коллекция", "expression"),
            ],
        ),
        (
            "loop_while",
            "Цикл while",
            "control",
            "orange",
            "repeat",
            "while (cond) { }",
            [
                _field("cond", "Условие", "expression"),
                _field("do_while", "do-while", "boolean", required=False, default=False),
            ],
        ),
        (
            "try",
            "Try/catch",
            "control",
            "orange",
            "shield",
            "try { } catch (Exception e) { }",
            [
                _field(
                    "exception_type", "Тип исключения", "type", required=False, default="Exception"
                ),
                _field("name", "Имя", "identifier", required=False, default="e"),
                _field("add_finally", "Добавить finally", "boolean", required=False, default=False),
            ],
        ),
        (
            "throw",
            "Throw",
            "control",
            "orange",
            "octagon-alert",
            'throw new IllegalStateException("…");',
            [_field("expr", "Исключение", "expression")],
        ),
        (
            "break",
            "Break",
            "advanced",
            "teal",
            "log-out",
            "break;",
            [_field("label", "Метка", "identifier", required=False)],
        ),
        (
            "continue",
            "Continue",
            "advanced",
            "teal",
            "skip-forward",
            "continue;",
            [_field("label", "Метка", "identifier", required=False)],
        ),
        (
            "code",
            "Код",
            "advanced",
            "teal",
            "code",
            "// произвольный код",
            [_field("text", "Код", "text")],
        ),
    ]
    return schemas.Palette(
        blocks=[
            schemas.PaletteBlock(
                kind=kind,  # type: ignore[arg-type]
                title=title,
                group=group,  # type: ignore[arg-type]
                color=color,
                icon=icon,
                fields=fields,
                template=template,
            )
            for kind, title, group, color, icon, template, fields in blocks
        ]
    )


__all__ = ["VersionInfo", "apply", "check_expression", "palette", "validate"]
