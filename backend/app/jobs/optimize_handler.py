"""Пакетная оптимизация (S8.6): шаги по очереди — «кандидат → gate → HEAD или пропуск»."""

from __future__ import annotations

import dataclasses

from sqlmodel import Session

from app.db.models import Project, RunStatus
from app.db.session import get_engine
from app.jobs.handlers import cancelled
from app.jobs.run_manager import Handler, JobContext, Outcome
from app.jobs.verify_handlers import run_gate
from app.schemas import verify as schemas
from app.services import analysis as analysis_service
from app.services import fixes as fixes_service
from app.services import versions as versions_service
from engine.analysis import analyzer
from engine.edit.core import EditError
from engine.java.project import get_project
from engine.transform.base import apply_proposal
from engine.transform.fixes import propose


def _step(
    ctx: JobContext, step_id: str, title: str, status: str, reason: str | None = None
) -> None:
    ctx.emit(
        schemas.StepEvent(
            data=schemas.StepData(step_id=step_id, title=title, status=status, reason=reason)  # type: ignore[arg-type]
        )
    )


def _apply_step(ctx: JobContext, finding_id: str) -> tuple[str, str | None]:
    """Применяет одно исправление к HEAD; возвращает ``(заголовок, причина пропуска или None)``."""
    with Session(get_engine()) as session:
        project = session.get(Project, ctx.project_id)
        assert project is not None
        head = versions_service.head_version(session, project)
        java = get_project(versions_service.version_files(session, head.id or 0))
        thresholds = analysis_service.thresholds(project, ctx.settings)
        finding = next(
            (f for f in analyzer.analyze(java, thresholds).findings if f.id == finding_id), None
        )
        if finding is None:
            return finding_id, "находка пропала после предыдущих шагов"
        proposal = propose(java, finding)
        if proposal is None:
            return finding_id, "для находки нет автоисправления"
        if not proposal.available:
            failed = proposal.failed()
            return proposal.title, (
                failed[0].reason if failed else None
            ) or "предусловия не выполнены"
        if not proposal.behavior_preserving:
            return proposal.title, "исправление меняет поведение: применяйте его отдельно"
        try:
            files = apply_proposal(java, proposal)
        except EditError as error:
            return proposal.title, error.message
        candidate = fixes_service.create_candidate(
            session, project, head, proposal, files, finding.id
        )
        candidate_id = candidate.id or 0
        title = proposal.title

    ctx.state.candidate = None
    gate = run_gate(
        dataclasses.replace(ctx, version_id=candidate_id, request=schemas.RunRequest(kind="gate"))
    )
    if ctx.state.candidate == "promoted":
        return title, None
    return title, gate.summary.message or "gate не пройден"


def run_optimize(ctx: JobContext) -> Outcome:
    """Исправления из ``step_ids`` применяются последовательно; каждый HEAD прошёл gate."""
    steps = ctx.request.step_ids or []
    applied: list[str] = []
    skipped: dict[str, str] = {}
    for index, finding_id in enumerate(steps):
        if ctx.cancel.is_set():
            return cancelled()
        _step(ctx, finding_id, finding_id, "applying")
        title, reason = _apply_step(ctx, finding_id)
        if reason is None:
            applied.append(finding_id)
            _step(ctx, finding_id, title, "passed")
        else:
            skipped[finding_id] = reason
            _step(ctx, finding_id, title, "skipped", reason)
        ctx.emit(schemas.ProgressEvent(data=schemas.ProgressData(done=index + 1, total=len(steps))))

    with Session(get_engine()) as session:
        project = session.get(Project, ctx.project_id)
        assert project is not None
        head = versions_service.head_version(session, project)
        java = get_project(versions_service.version_files(session, head.id or 0))
        after = analyzer.analyze(java, analysis_service.thresholds(project, ctx.settings))
        head_id, gate_status = head.id or 0, head.gate_status
    summary = schemas.RunSummary(
        passed=len(applied),
        total=len(steps),
        version_status=gate_status if gate_status in {"passed", "failed"} else "unknown",  # type: ignore[arg-type]
        message=f"Применено шагов: {len(applied)} из {len(steps)}",
        data={
            "applied": applied,
            "skipped": skipped,
            "head_version_id": head_id,
            "complexity_after": after.complexity.current,
        },
    )
    return Outcome(RunStatus.DONE.value, summary)


def optimize_handlers() -> dict[str, Handler]:
    return {"optimize": run_optimize}
