"""Отчёты: запуск (JSON, Markdown, JUnit XML), сводный отчёт версии и комплект сдачи (S6.4, docs/07 § 5)."""

from __future__ import annotations

import io
import json
import re
import zipfile
from typing import Any
from xml.etree import ElementTree as ET

from sqlmodel import Session, col, select

from app.db.models import Project, Run, Version
from app.errors import bad_request
from app.schemas import verify as schemas
from app.services import runs as runs_service
from app.services import scenarios as scenarios_service
from app.services import versions as versions_service

_ZIP_TIME = (2020, 1, 1, 0, 0, 0)
_XML_ILLEGAL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")
_VERDICT_MARK = {"PASS": "✓", "FAIL": "✗", "ERROR": "!", "TIMEOUT": "⏱"}
_GATE_TEXT = {"passed": "совпадает", "failed": "отличается", "unknown": "не проверено"}


def _dump(model: Any) -> Any:
    return json.loads(model.model_dump_json())


def _json_bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _version_block(version: Version | None) -> dict[str, Any] | None:
    if version is None:
        return None
    return {
        "id": version.id,
        "number": version.number,
        "origin": version.origin,
        "description": version.description,
        "content_hash": version.content_hash,
        "gate_status": version.gate_status,
        "created_at": version.created_at.isoformat(),
    }


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _seconds(ms: int | None) -> str:
    return "—" if ms is None else f"{ms / 1000:.2f} с"


# --- отчёт запуска ----------------------------------------------------------------------------------------


def run_context(session: Session, run: Run) -> dict[str, Any]:
    project = session.get(Project, run.project_id)
    version = session.get(Version, run.version_id) if run.version_id else None
    baseline = (
        session.get(Version, project.baseline_version_id)
        if project and project.baseline_version_id
        else None
    )
    return {
        "project": {"id": project.id, "name": project.name} if project else None,
        "version": _version_block(version),
        "baseline_version": _version_block(baseline),
    }


def run_json(session: Session, run: Run) -> bytes:
    info = runs_service.info(session, run)
    return _json_bytes({**run_context(session, run), "run": _dump(info)})


def _diff_lines(item: schemas.RunItem) -> list[str]:
    diff = item.diff
    if diff is None:
        return []
    lines: list[str] = []
    if diff.stdout:
        lines += [
            "",
            f"**{item.name}: stdout**",
            "",
            "```diff",
            diff.stdout.unified.rstrip("\n"),
            "```",
        ]
    if diff.stderr:
        lines += [
            "",
            f"**{item.name}: stderr**",
            "",
            "```diff",
            diff.stderr.unified.rstrip("\n"),
            "```",
        ]
    if diff.exit_code:
        lines += [
            "",
            f"**{item.name}: код выхода** — ожидался {diff.exit_code.expected}, получен {diff.exit_code.actual}",
        ]
    if diff.exception:
        lines += [
            "",
            f"**{item.name}: исключение** — ожидалось {diff.exception.expected or '—'}, "
            f"получено {diff.exception.actual or '—'}",
        ]
    return lines


def run_markdown(session: Session, run: Run) -> bytes:
    info = runs_service.info(session, run)
    context = run_context(session, run)
    version, baseline = context["version"], context["baseline_version"]
    project = context["project"] or {}
    lines = [f"# Отчёт запуска {run.id}: {run.kind}", ""]
    lines.append(f"- Проект: {project.get('name', '—')}")
    if version:
        lines.append(
            f"- Версия: {version['number']} — {version['description']} (`{version['content_hash'][:12]}`)"
        )
    if baseline:
        lines.append(f"- Эталонная версия: {baseline['number']} — {baseline['description']}")
    lines.append(f"- Статус запуска: {info.status}")
    summary = info.summary
    if summary.version_status:
        lines.append(
            f"- Поведение: {_GATE_TEXT.get(summary.version_status, summary.version_status)}"
        )
    if summary.message:
        lines.append(f"- Итог: {summary.message}")
    if info.items:
        lines += ["", "| Тест | Результат | Время | Эталон |", "|---|---|---|---|"]
        for item in info.items:
            mark = f"{_VERDICT_MARK.get(item.verdict, '?')} {item.verdict}"
            lines.append(
                f"| {_cell(item.name)} | {mark} | {_seconds(item.duration_ms)} | {_seconds(item.baseline_ms)} |"
            )
        for item in info.items:
            lines += _diff_lines(item)
    data = summary.data or {}
    warnings = data.get("warnings") or []
    if warnings:
        lines += ["", "## Предупреждения", ""] + [f"- {w}" for w in warnings]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _xml_text(text: str) -> str:
    return _XML_ILLEGAL.sub("", text)


def run_junit(session: Session, run: Run) -> bytes:
    info = runs_service.info(session, run)
    project = session.get(Project, run.project_id)
    suite_name = f"{project.name if project else 'project'} #{run.id} ({run.kind})"
    failures = sum(1 for i in info.items if i.verdict == "FAIL")
    errors = sum(1 for i in info.items if i.verdict in {"ERROR", "TIMEOUT"})
    total_time = sum(i.duration_ms for i in info.items) / 1000
    suites = ET.Element("testsuites")
    suite = ET.SubElement(
        suites,
        "testsuite",
        name=_xml_text(suite_name),
        tests=str(len(info.items)),
        failures=str(failures),
        errors=str(errors),
        skipped="0",
        time=f"{total_time:.3f}",
    )
    for item in info.items:
        case = ET.SubElement(
            suite,
            "testcase",
            classname=_xml_text(suite_name),
            name=_xml_text(item.name),
            time=f"{item.duration_ms / 1000:.3f}",
        )
        if item.verdict == "FAIL":
            parts = []
            if item.diff and item.diff.stdout:
                parts.append(item.diff.stdout.unified)
            if item.diff and item.diff.exit_code:
                parts.append(
                    f"код выхода: ожидался {item.diff.exit_code.expected}, получен {item.diff.exit_code.actual}"
                )
            if item.diff and item.diff.exception:
                parts.append(f"исключение: {item.diff.exception.actual}")
            failure = ET.SubElement(
                case, "failure", message="поведение отличается от эталона", type="BehaviorDiff"
            )
            failure.text = _xml_text("\n".join(parts) or item.stdout)
        elif item.verdict in {"ERROR", "TIMEOUT"}:
            error = ET.SubElement(case, "error", message=item.verdict, type=item.verdict)
            error.text = _xml_text(item.stderr)
        if item.stdout:
            ET.SubElement(case, "system-out").text = _xml_text(item.stdout)
    ET.indent(suites)
    body = ET.tostring(suites, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{body}\n'.encode()


RUN_FORMATS: dict[str, tuple[str, Any]] = {
    "json": ("application/json", run_json),
    "md": ("text/markdown; charset=utf-8", run_markdown),
    "junit": ("application/xml", run_junit),
}


def run_report(session: Session, run: Run, fmt: str) -> tuple[bytes, str, str]:
    """``(тело, media type, имя файла)`` отчёта запуска."""
    if fmt not in RUN_FORMATS:
        raise bad_request(f"неизвестный формат отчёта: {fmt}")
    media, build = RUN_FORMATS[fmt]
    extension = {"json": "json", "md": "md", "junit": "xml"}[fmt]
    return build(session, run), media, f"run-{run.id}-{run.kind}.{extension}"


# --- сводный отчёт версии --------------------------------------------------------------------------------


def latest_check(session: Session, project: Project, version: Version) -> Run | None:
    query = (
        select(Run)
        .where(
            Run.project_id == project.id,
            Run.version_id == version.id,
            col(Run.kind).in_(["gate", "test"]),
            Run.status == "done",
        )
        .order_by(col(Run.id).desc())
    )
    return session.exec(query).first()


def project_data(session: Session, project: Project, version: Version) -> dict[str, Any]:
    check = latest_check(session, project, version)
    baseline = (
        session.get(Version, project.baseline_version_id) if project.baseline_version_id else None
    )
    history = runs_service.history(session, project, limit=20)
    return {
        "project": {"id": project.id, "name": project.name, "main_class": project.main_class},
        "version": _version_block(version),
        "baseline_version": _version_block(baseline),
        "scenarios": _dump(
            schemas.ScenarioList(scenarios=scenarios_service.listing(session, project))
        ),
        "behavior": _dump(runs_service.info(session, check)) if check else None,
        "runs": [
            {
                "id": r.id,
                "kind": r.kind,
                "status": r.status,
                "version_id": r.version_id,
                "message": r.summary.message,
            }
            for r in history
        ],
    }


def project_markdown(data: dict[str, Any]) -> bytes:
    project, version, baseline = data["project"], data["version"], data["baseline_version"]
    lines = [f"# Сводный отчёт: {project['name']}", ""]
    lines.append(
        f"- Версия: {version['number']} — {version['description']} (`{version['content_hash'][:12]}`)"
    )
    lines.append(
        f"- Проверка поведения: {_GATE_TEXT.get(version['gate_status'], version['gate_status'])}"
    )
    if baseline:
        lines.append(f"- Эталонная версия: {baseline['number']} — {baseline['description']}")
    lines.append(f"- Главный класс: {project['main_class'] or '—'}")
    behavior = data["behavior"]
    if behavior:
        summary = behavior["summary"]
        lines += ["", "## Результаты тестов", "", f"{summary.get('message') or ''}", ""]
        lines += ["| Тест | Результат | Время | Эталон |", "|---|---|---|---|"]
        for item in behavior["items"]:
            mark = f"{_VERDICT_MARK.get(item['verdict'], '?')} {item['verdict']}"
            lines.append(
                f"| {_cell(item['name'])} | {mark} | {_seconds(item['duration_ms'])} | {_seconds(item['baseline_ms'])} |"
            )
    else:
        lines += ["", "## Результаты тестов", "", "Проверка этой версии не запускалась."]
    scenarios = data["scenarios"]["scenarios"]
    lines += ["", f"## Сценарии ({len(scenarios)})", ""]
    if scenarios:
        lines += ["| Имя | Источник | Эталон | Стабильность | Включён |", "|---|---|---|---|---|"]
        for s in scenarios:
            lines.append(
                f"| {_cell(s['name'])} | {s['source']} | {s['baseline']['state']} | {s['stability']} | "
                f"{'да' if s['enabled'] else 'нет'} |"
            )
    lines += ["", "## История запусков", ""]
    if data["runs"]:
        lines += ["| № | Вид | Статус | Итог |", "|---|---|---|---|"]
        lines += [
            f"| {r['id']} | {r['kind']} | {r['status']} | {_cell(r['message'] or '')} |"
            for r in data["runs"]
        ]
    else:
        lines.append("Запусков не было.")
    return ("\n".join(lines) + "\n").encode("utf-8")


def project_report(
    session: Session, project: Project, version: Version, fmt: str
) -> tuple[bytes, str, str]:
    data = project_data(session, project, version)
    if fmt == "json":
        return _json_bytes(data), "application/json", f"report-v{version.number}.json"
    if fmt == "md":
        return (
            project_markdown(data),
            "text/markdown; charset=utf-8",
            f"report-v{version.number}.md",
        )
    raise bad_request(f"неизвестный формат отчёта: {fmt}")


# --- комплект сдачи ----------------------------------------------------------------------------------------


def bundle(session: Session, project: Project, version: Version) -> bytes:
    """Zip: исходники версии, отчёты и сценарии; достаточен для воспроизведения проверки."""
    files = versions_service.version_files(session, version.id or 0)
    data = project_data(session, project, version)
    entries: dict[str, bytes] = {
        f"src/{path}": text.encode("utf-8") for path, text in files.items()
    }
    entries["reports/report.md"] = project_markdown(data)
    entries["reports/report.json"] = _json_bytes(data)
    check = latest_check(session, project, version)
    if check is not None:
        entries["reports/junit.xml"] = run_junit(session, check)
    exported = scenarios_service.export(session, project)
    entries["scenarios/scenarios.json"] = _json_bytes(_dump(exported))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, _ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, entries[name])
    return buffer.getvalue()
