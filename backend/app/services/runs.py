"""Запуски в БД: создание, итог, история, восстановление событий (S3.6)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, col, select

from app.db.models import Project, Run, RunItem, RunStatus
from app.errors import not_found
from app.schemas import verify as schemas

ACTIVE = (RunStatus.QUEUED.value, RunStatus.RUNNING.value)
INTERRUPTED = "прерван перезапуском сервера"


def get_or_404(session: Session, run_id: int) -> Run:
    run = session.get(Run, run_id)
    if run is None:
        raise not_found(f"запуск {run_id} не найден", run_id=run_id)
    return run


def create(session: Session, project_id: int, kind: str, version_id: int) -> Run:
    run = Run(project_id=project_id, version_id=version_id, kind=kind)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def mark_started(session: Session, run_id: int) -> None:
    run = session.get(Run, run_id)
    if run is not None:
        run.status = RunStatus.RUNNING.value
        run.started_at = datetime.now(UTC)
        session.add(run)
        session.commit()


def finish(
    session: Session,
    run_id: int,
    status: str,
    summary: schemas.RunSummary,
    items: list[schemas.RunItem],
) -> None:
    run = session.get(Run, run_id)
    if run is None:
        return
    run.status = status
    run.finished_at = datetime.now(UTC)
    run.summary = summary.model_dump(mode="json")
    session.add(run)
    for item in items:
        session.add(
            RunItem(
                run_id=run_id,
                scenario_id=item.scenario_id,
                name=item.name,
                status=item.verdict,
                stdout=item.stdout,
                stderr=item.stderr,
                exit_code=item.exit_code,
                duration_ms=item.duration_ms,
                baseline_ms=item.baseline_ms,
                diff=item.diff.model_dump(mode="json") if item.diff else None,
                hits=item.hits,
            )
        )
    session.commit()


def mark_interrupted(session: Session) -> int:
    """При старте сервера незавершённые запуски помечаются ошибкой: их процессов уже нет."""
    stale = session.exec(select(Run).where(col(Run.status).in_(ACTIVE))).all()
    summary = schemas.RunSummary(message=INTERRUPTED).model_dump(mode="json")
    for run in stale:
        run.status = RunStatus.ERROR.value
        run.finished_at = datetime.now(UTC)
        run.summary = summary
        session.add(run)
    session.commit()
    return len(stale)


def _item(row: RunItem) -> schemas.RunItem:
    return schemas.RunItem(
        scenario_id=row.scenario_id,
        name=row.name,
        verdict=row.status,  # type: ignore[arg-type]
        stdout=row.stdout,
        stderr=row.stderr,
        exit_code=row.exit_code,
        duration_ms=row.duration_ms or 0,
        baseline_ms=row.baseline_ms,
        diff=schemas.BehaviorDiff.model_validate(row.diff) if row.diff else None,
        hits=row.hits,
    )


def items_of(session: Session, run_id: int) -> list[schemas.RunItem]:
    rows = session.exec(
        select(RunItem).where(RunItem.run_id == run_id).order_by(col(RunItem.id))
    ).all()
    return [_item(row) for row in rows]


def info(session: Session, run: Run) -> schemas.RunInfo:
    return schemas.RunInfo(
        id=run.id or 0,
        kind=run.kind,  # type: ignore[arg-type]
        status=run.status,  # type: ignore[arg-type]
        version_id=run.version_id,
        started_at=run.started_at,
        finished_at=run.finished_at,
        summary=schemas.RunSummary.model_validate(run.summary or {}),
        items=items_of(session, run.id or 0),
    )


def history(session: Session, project: Project, limit: int = 50) -> list[schemas.RunInfo]:
    query = (
        select(Run).where(Run.project_id == project.id).order_by(col(Run.id).desc()).limit(limit)
    )
    return [info(session, run) for run in session.exec(query).all()]


def replay_events(run: schemas.RunInfo) -> list[Any]:
    """События завершённого запуска, которого нет в памяти (после перезапуска): по данным из БД."""
    events: list[Any] = [schemas.StatusEvent(data=schemas.StatusData(status="running"))]
    for item in run.items:
        events.append(
            schemas.ItemEvent(
                data=schemas.ItemData(
                    scenario_id=item.scenario_id,
                    name=item.name,
                    verdict=item.verdict,
                    duration_ms=item.duration_ms,
                    baseline_ms=item.baseline_ms,
                    diff=item.diff,
                )
            )
        )
    events.append(schemas.ResultEvent(data=schemas.ResultData(summary=run.summary)))
    events.append(schemas.StatusEvent(data=schemas.StatusData(status=run.status)))
    events.append(schemas.DoneEvent(data=schemas.DoneData()))
    return events
