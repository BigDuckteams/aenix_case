"""Сценарии проекта: CRUD, импорт/экспорт, статус эталона (S6.1, docs/07 § 3)."""

from __future__ import annotations

import re
from collections.abc import Sequence

from sqlmodel import Session, col, delete, select

from app.db.models import Baseline, Project
from app.db.models import Scenario as ScenarioRow
from app.errors import bad_request, not_found
from app.schemas import verify as schemas
from engine.verify.normalize import Mask

MAX_STDIN_BYTES = 2 * 1024 * 1024
MAX_SCENARIOS = 500


def get_or_404(session: Session, project: Project, scenario_id: int) -> ScenarioRow:
    row = session.get(ScenarioRow, scenario_id)
    if row is None or row.project_id != project.id:
        raise not_found(f"сценарий {scenario_id} не найден", scenario_id=scenario_id)
    return row


def rows(session: Session, project: Project) -> list[ScenarioRow]:
    query = (
        select(ScenarioRow)
        .where(ScenarioRow.project_id == project.id)
        .order_by(col(ScenarioRow.id))
    )
    return list(session.exec(query).all())


def baselines(session: Session, project: Project) -> dict[int, Baseline]:
    found = session.exec(select(Baseline).where(Baseline.project_id == project.id)).all()
    return {b.scenario_id: b for b in found}


def masks_of(row: ScenarioRow) -> list[Mask]:
    return [Mask(m["pattern"], m["replacement"]) for m in row.masks or []]


def baseline_status(project: Project, baseline: Baseline | None) -> schemas.BaselineStatus:
    if baseline is None:
        return schemas.BaselineStatus(state="none")
    stale = baseline.version_id != project.baseline_version_id
    return schemas.BaselineStatus(
        state="stale" if stale else "recorded",
        version_id=baseline.version_id,
        duration_ms=baseline.duration_ms,
    )


def to_schema(project: Project, row: ScenarioRow, baseline: Baseline | None) -> schemas.Scenario:
    return schemas.Scenario(
        id=row.id or 0,
        name=row.name,
        description=row.description,
        stdin=row.stdin,
        args=list(row.args or []),
        source=row.source,  # type: ignore[arg-type]
        size_factor=row.size_factor,
        enabled=row.enabled,
        stability=row.stability,  # type: ignore[arg-type]
        masks=[schemas.Mask(**m) for m in row.masks or []],
        baseline=baseline_status(project, baseline),
        created_at=row.created_at,
    )


def listing(session: Session, project: Project) -> list[schemas.Scenario]:
    stored = baselines(session, project)
    return [to_schema(project, row, stored.get(row.id or 0)) for row in rows(session, project)]


def _check_input(stdin: str, args: Sequence[str]) -> None:
    if len(stdin.encode("utf-8")) > MAX_STDIN_BYTES:
        raise bad_request("stdin больше 2 МБ")
    if any("\0" in a for a in args):
        raise bad_request("аргументы не могут содержать нулевой символ")


def _check_masks(masks: Sequence[schemas.Mask]) -> list[dict[str, str]]:
    for mask in masks:
        try:
            re.compile(mask.pattern)
        except re.error as exc:
            raise bad_request(
                f"неверная маска «{mask.pattern}»: {exc}", pattern=mask.pattern
            ) from exc
    return [{"pattern": m.pattern, "replacement": m.replacement} for m in masks]


def _unique_name(session: Session, project: Project, name: str) -> str:
    taken = {r.name for r in rows(session, project)}
    if name not in taken:
        return name
    number = 2
    while f"{name} ({number})" in taken:
        number += 1
    return f"{name} ({number})"


def _ensure_capacity(session: Session, project: Project, adding: int = 1) -> None:
    if len(rows(session, project)) + adding > MAX_SCENARIOS:
        raise bad_request(f"в проекте не может быть больше {MAX_SCENARIOS} сценариев")


def create(session: Session, project: Project, payload: schemas.ScenarioCreate) -> schemas.Scenario:
    name = payload.name.strip()
    if not name:
        raise bad_request("у сценария должно быть имя")
    _check_input(payload.stdin, payload.args)
    _ensure_capacity(session, project)
    if name in {r.name for r in rows(session, project)}:
        raise bad_request(f"сценарий «{name}» уже есть", name=name)
    row = ScenarioRow(
        project_id=project.id or 0,
        name=name,
        description=payload.description,
        stdin=payload.stdin,
        args=list(payload.args),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return to_schema(project, row, None)


def update(
    session: Session, project: Project, scenario_id: int, payload: schemas.ScenarioUpdate
) -> schemas.Scenario:
    row = get_or_404(session, project, scenario_id)
    reset = False
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise bad_request("у сценария должно быть имя")
        if name != row.name and name in {r.name for r in rows(session, project)}:
            raise bad_request(f"сценарий «{name}» уже есть", name=name)
        row.name = name
    if payload.description is not None:
        row.description = payload.description
    if payload.enabled is not None:
        row.enabled = payload.enabled
    if payload.stdin is not None and payload.stdin != row.stdin:
        row.stdin, reset = payload.stdin, True
    if payload.args is not None and list(payload.args) != list(row.args or []):
        row.args, reset = list(payload.args), True
    if payload.masks is not None:
        stored = _check_masks(payload.masks)
        if stored != (row.masks or []):
            row.masks, reset = stored, True
    _check_input(row.stdin, row.args or [])
    if reset:
        session.exec(delete(Baseline).where(Baseline.scenario_id == row.id))  # type: ignore[call-overload]
        row.stability = "stable"
    session.add(row)
    session.commit()
    session.refresh(row)
    return to_schema(project, row, baselines(session, project).get(row.id or 0))


def remove(session: Session, project: Project, scenario_id: int) -> None:
    row = get_or_404(session, project, scenario_id)
    session.exec(delete(Baseline).where(Baseline.scenario_id == row.id))  # type: ignore[call-overload]
    session.delete(row)
    session.commit()


def import_items(
    session: Session, project: Project, payload: schemas.ScenarioImport
) -> schemas.ScenarioImportResult:
    _ensure_capacity(session, project, len(payload.scenarios))
    warnings: list[str] = []
    created: list[ScenarioRow] = []
    for item in payload.scenarios:
        name = item.name.strip()
        if not name:
            raise bad_request("у сценария должно быть имя")
        _check_input(item.stdin, item.args)
        unique = _unique_name(session, project, name)
        if unique != name:
            warnings.append(f"имя «{name}» занято, сценарий импортирован как «{unique}»")
        row = ScenarioRow(
            project_id=project.id or 0,
            name=unique,
            description=item.description,
            stdin=item.stdin,
            args=list(item.args),
            source="imported",
            expected_stdout=item.expected_stdout,
            expected_exit_code=item.expected_exit_code,
        )
        session.add(row)
        session.flush()
        created.append(row)
    session.commit()
    return schemas.ScenarioImportResult(
        imported=len(created), scenario_ids=[r.id or 0 for r in created], warnings=warnings
    )


def export(session: Session, project: Project) -> schemas.ScenarioExport:
    stored = baselines(session, project)
    items: list[schemas.ScenarioExportItem] = []
    for row in rows(session, project):
        baseline = stored.get(row.id or 0)
        expected = (
            row.expected_stdout
            if row.expected_stdout is not None
            else (baseline.stdout if baseline else None)
        )
        exit_code = (
            row.expected_exit_code
            if row.expected_exit_code is not None
            else (baseline.exit_code if baseline else None)
        )
        items.append(
            schemas.ScenarioExportItem(
                name=row.name,
                description=row.description,
                stdin=row.stdin,
                args=list(row.args or []),
                expected_stdout=expected,
                expected_exit_code=exit_code,
            )
        )
    return schemas.ScenarioExport(scenarios=items)
