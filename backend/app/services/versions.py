"""Версии проекта: цепочка, HEAD, undo/redo, восстановление, правки файлов, diff (S3.1, S3.3).

Версия — неизменяемый снимок всех файлов. Исключение одно: подряд идущие правки кода
(``code_edit``) схлопываются в HEAD, пока у него нет потомков (docs/08-api.md § 3).
"""

from __future__ import annotations

import difflib
import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, col, select

from app.db.models import GateStatus, Project, SourceFile, Version, VersionOrigin, VersionStatus
from app.errors import ApiError, bad_request, not_found, version_conflict
from app.schemas.common import FileDiff, FileEntry, SourceRange, SyntaxIssue
from app.schemas.project import VersionChange, VersionInfo
from engine.java.project import JavaProject, content_hash_of


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- чтение ------------------------------------------------------------------------------------


def version_files(session: Session, version_id: int) -> dict[str, str]:
    rows = session.exec(select(SourceFile).where(SourceFile.version_id == version_id)).all()
    return {row.path: row.content for row in sorted(rows, key=lambda r: r.path)}


def get_version(session: Session, project: Project, version_id: int) -> Version:
    version = session.get(Version, version_id)
    if version is None or version.project_id != project.id:
        raise not_found(f"версия {version_id} не найдена", version_id=version_id)
    return version


def get_version_by_id(session: Session, version_id: int) -> Version:
    version = session.get(Version, version_id)
    if version is None:
        raise not_found(f"версия {version_id} не найдена", version_id=version_id)
    return version


def head_version(session: Session, project: Project) -> Version:
    if project.head_version_id is None:
        raise not_found("у проекта нет версий")
    return get_version(session, project, project.head_version_id)


def resolve_version(session: Session, project: Project, version_id: int | None) -> Version:
    """Версия из запроса или HEAD (``?version_id`` необязателен, docs/08-api.md § 1)."""
    if version_id is None:
        return head_version(session, project)
    return get_version(session, project, version_id)


def list_versions(session: Session, project: Project) -> list[Version]:
    query = (
        select(Version).where(Version.project_id == project.id).order_by(col(Version.number).desc())
    )
    return list(session.exec(query).all())


def children(session: Session, version: Version) -> list[Version]:
    query = select(Version).where(Version.parent_id == version.id).order_by(col(Version.number))
    return list(session.exec(query).all())


def version_info(version: Version) -> VersionInfo:
    return VersionInfo(
        id=version.id or 0,
        number=version.number,
        parent_id=version.parent_id,
        origin=version.origin,  # type: ignore[arg-type]
        description=version.description,
        created_at=version.created_at,
        gate_status=version.gate_status,  # type: ignore[arg-type]
        status=version.status,  # type: ignore[arg-type]
        content_hash=version.content_hash,
    )


def file_entries(files: Mapping[str, str]) -> list[FileEntry]:
    return [
        FileEntry(path=path, lines=len(text.splitlines()), size=len(text.encode("utf-8")))
        for path, text in sorted(files.items())
    ]


def syntax_issues(project: JavaProject, only: set[str] | None = None) -> list[SyntaxIssue]:
    """Синтаксические ошибки файлов (все или перечисленные) в формате API."""
    issues: list[SyntaxIssue] = []
    for path, found in project.syntax_issues().items():
        if only is not None and path not in only:
            continue
        for issue in found:
            span = issue.range
            issues.append(
                SyntaxIssue(
                    message=issue.message,
                    range=SourceRange(
                        file=path,
                        start_line=span.start.line,
                        start_col=span.start.column,
                        end_line=span.end.line,
                        end_col=span.end.column,
                    ),
                )
            )
    return issues


# --- создание версий ------------------------------------------------------------------------------


def create_version(
    session: Session,
    project: Project,
    files: Mapping[str, str],
    *,
    origin: VersionOrigin | str,
    description: str,
    parent_id: int | None,
    status: VersionStatus | str = VersionStatus.ACTIVE,
    meta: dict[str, Any] | None = None,
    make_head: bool = True,
) -> Version:
    last = session.exec(
        select(Version).where(Version.project_id == project.id).order_by(col(Version.number).desc())
    ).first()
    version = Version(
        project_id=project.id or 0,
        number=(last.number + 1) if last else 1,
        parent_id=parent_id,
        origin=str(origin.value if isinstance(origin, VersionOrigin) else origin),
        description=description,
        content_hash=content_hash_of(files),
        status=str(status.value if isinstance(status, VersionStatus) else status),
        gate_status=GateStatus.UNKNOWN.value,
        meta=meta or {},
    )
    session.add(version)
    session.flush()
    for path, text in sorted(files.items()):
        session.add(
            SourceFile(version_id=version.id or 0, path=path, content=text, sha256=sha256(text))
        )
    if make_head and version.status == VersionStatus.ACTIVE.value:
        project.head_version_id = version.id
        project.updated_at = datetime.now(UTC)
        session.add(project)
    session.commit()
    session.refresh(version)
    return version


def _changed_paths(old: Mapping[str, str], new: Mapping[str, str]) -> list[str]:
    return sorted(p for p in set(old) | set(new) if old.get(p) != new.get(p))


def _change(
    session: Session,
    project: Project,
    version: Version,
    old: Mapping[str, str],
    *,
    collapsed: bool = False,
) -> VersionChange:
    files = version_files(session, version.id or 0)
    changed = _changed_paths(old, files)
    from engine.java.project import get_project

    issues = syntax_issues(get_project(files), set(changed) & set(files))
    return VersionChange(
        version=version_info(version),
        head_version_id=project.head_version_id or version.id or 0,
        changed_files=changed,
        syntax_errors=issues,
        collapsed=collapsed,
    )


def require_head(project: Project, base_version_id: int) -> None:
    if base_version_id != project.head_version_id:
        raise version_conflict(
            "версия устарела: HEAD проекта изменился",
            base_version_id=base_version_id,
            head_version_id=project.head_version_id,
        )


# --- правки файлов ----------------------------------------------------------------------------------


def save_file(
    session: Session, project: Project, path: str, content: str, base_version_id: int
) -> VersionChange:
    """``PUT /files/{path}``: новая версия ``code_edit`` или схлопывание в HEAD."""
    require_head(project, base_version_id)
    head = head_version(session, project)
    old = version_files(session, head.id or 0)
    if path not in old:
        raise not_found(f"файл {path} не найден", path=path)
    if old[path] == content:
        return _change(session, project, head, old)
    new = {**old, path: content}

    if head.origin == VersionOrigin.CODE_EDIT.value and not children(session, head):
        row = session.exec(
            select(SourceFile).where(SourceFile.version_id == head.id, SourceFile.path == path)
        ).one()
        row.content = content
        row.sha256 = sha256(content)
        head.content_hash = content_hash_of(new)
        head.gate_status = GateStatus.UNKNOWN.value
        head.gate_run_id = None
        project.updated_at = datetime.now(UTC)
        session.add_all([row, head, project])
        session.commit()
        session.refresh(head)
        return _change(session, project, head, old, collapsed=True)

    version = create_version(
        session,
        project,
        new,
        origin=VersionOrigin.CODE_EDIT,
        description=f"Правка {path}",
        parent_id=head.id,
    )
    return _change(session, project, version, old)


def create_file(session: Session, project: Project, path: str, content: str) -> VersionChange:
    head = head_version(session, project)
    old = version_files(session, head.id or 0)
    if path in old:
        raise bad_request(f"файл {path} уже существует", path=path)
    version = create_version(
        session,
        project,
        {**old, path: content},
        origin=VersionOrigin.CODE_EDIT,
        description=f"Создан файл {path}",
        parent_id=head.id,
    )
    return _change(session, project, version, old)


def delete_file(session: Session, project: Project, path: str) -> VersionChange:
    head = head_version(session, project)
    old = version_files(session, head.id or 0)
    if path not in old:
        raise not_found(f"файл {path} не найден", path=path)
    if len(old) == 1:
        raise bad_request("нельзя удалить последний файл проекта")
    remaining = {p: t for p, t in old.items() if p != path}
    version = create_version(
        session,
        project,
        remaining,
        origin=VersionOrigin.CODE_EDIT,
        description=f"Удалён файл {path}",
        parent_id=head.id,
    )
    return _change(session, project, version, old)


# --- навигация по версиям ---------------------------------------------------------------------------


def _move_head(session: Session, project: Project, target: Version) -> VersionChange:
    old_head = head_version(session, project)
    old = version_files(session, old_head.id or 0)
    project.head_version_id = target.id
    project.updated_at = datetime.now(UTC)
    session.add(project)
    session.commit()
    session.refresh(target)
    return _change(session, project, target, old)


def undo(session: Session, project: Project) -> VersionChange:
    head = head_version(session, project)
    if head.parent_id is None:
        raise bad_request("нечего отменять: это первая версия")
    return _move_head(session, project, get_version(session, project, head.parent_id))


def redo(session: Session, project: Project) -> VersionChange:
    head = head_version(session, project)
    forward = [v for v in children(session, head) if v.status == VersionStatus.ACTIVE.value]
    if not forward:
        raise bad_request("нечего повторять: у текущей версии нет потомков")
    return _move_head(session, project, forward[-1])


def restore(session: Session, project: Project, version_id: int) -> VersionChange:
    """Делает версию HEAD: создаётся новая версия ``revert`` с её файлами."""
    source = get_version(session, project, version_id)
    head = head_version(session, project)
    old = version_files(session, head.id or 0)
    version = create_version(
        session,
        project,
        version_files(session, source.id or 0),
        origin=VersionOrigin.REVERT,
        description=f"Восстановлена версия {source.number}",
        parent_id=head.id,
    )
    return _change(session, project, version, old)


# --- diff ------------------------------------------------------------------------------------------


def diff_files(old: Mapping[str, str], new: Mapping[str, str]) -> list[FileDiff]:
    result: list[FileDiff] = []
    for path in sorted(set(old) | set(new)):
        before, after = old.get(path), new.get(path)
        if before == after:
            continue
        status = "added" if before is None else "removed" if after is None else "modified"
        unified = "".join(
            difflib.unified_diff(
                (before or "").splitlines(keepends=True),
                (after or "").splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )
        result.append(
            FileDiff(path=path, status=status, unified=unified, before=before, after=after)
        )  # type: ignore[arg-type]
    return result


__all__ = [
    "ApiError",
    "children",
    "create_file",
    "create_version",
    "delete_file",
    "diff_files",
    "file_entries",
    "get_version",
    "head_version",
    "list_versions",
    "redo",
    "require_head",
    "resolve_version",
    "restore",
    "save_file",
    "syntax_issues",
    "undo",
    "version_files",
    "version_info",
]
