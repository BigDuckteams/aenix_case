"""Отчёты (S6.4): запуск в JSON/Markdown/JUnit, сводный отчёт версии и комплект сдачи (без JDK)."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from xml.etree import ElementTree as ET

import pytest
from sqlmodel import Session

from app.db.models import Run, RunItem, Scenario, Version


@pytest.fixture
def checked(client, make_project, session: Session):
    """Проект с завершённым запуском ``test``: один зелёный и один красный сценарий, одна ошибка."""
    project = make_project(name="отчёт")
    scenario = Scenario(project_id=project["id"], name="один", stdin="1\n")
    session.add(scenario)
    session.commit()
    run = Run(
        project_id=project["id"],
        version_id=project["head_version_id"],
        kind="test",
        status="done",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        summary={
            "passed": 1,
            "total": 3,
            "version_status": "failed",
            "message": "Поведение отличается: 1 из 3",
            "data": {"warnings": ["x: нет эталона"]},
        },
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    diff = {
        "stdout": {
            "expected": "11",
            "actual": "-9",
            "unified": "--- эталон\n+++ фактически\n@@\n-11\n+-9\n",
        },
        "exit_code": {"expected": 0, "actual": 1},
    }
    session.add_all(
        [
            RunItem(
                run_id=run.id,
                scenario_id=scenario.id,
                name="один",
                status="PASS",
                stdout="11",
                duration_ms=40,
                baseline_ms=35,
            ),
            RunItem(
                run_id=run.id,
                name="два | три",
                status="FAIL",
                stdout="-9\x01",
                exit_code=1,
                duration_ms=50,
                baseline_ms=30,
                diff=diff,
            ),
            RunItem(
                run_id=run.id, name="таймаут", status="TIMEOUT", stderr="slow", duration_ms=1000
            ),
        ]
    )
    session.commit()
    version = session.get(Version, project["head_version_id"])
    version.gate_status = "failed"
    session.add(version)
    session.commit()
    return project, run.id


def test_run_report_json(client, checked):
    project, run_id = checked
    response = client.get(f"/api/runs/{run_id}/report")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert f"run-{run_id}-test.json" in response.headers["content-disposition"]
    body = response.json()
    assert body["project"]["name"] == "отчёт"
    assert body["version"]["number"] == 1
    assert body["baseline_version"]["id"] == project["original_version_id"]
    assert body["run"]["summary"]["version_status"] == "failed"
    assert [i["verdict"] for i in body["run"]["items"]] == ["PASS", "FAIL", "TIMEOUT"]
    assert body["run"]["items"][1]["diff"]["stdout"]["actual"] == "-9"


def test_run_report_markdown_has_table_and_diff(client, checked):
    _, run_id = checked
    response = client.get(f"/api/runs/{run_id}/report", params={"format": "md"})
    assert response.headers["content-type"].startswith("text/markdown")
    text = response.text
    assert text.startswith(f"# Отчёт запуска {run_id}: test")
    assert "| один | ✓ PASS | 0.04 с | 0.04 с |" in text
    assert "✗ FAIL" in text and "⏱ TIMEOUT" in text
    assert "два \\| три" in text  # символ таблицы экранирован
    assert "```diff" in text and "+-9" in text
    assert "код выхода** — ожидался 0, получен 1" in text
    assert "- x: нет эталона" in text
    assert "Поведение: отличается" in text


def test_run_report_junit_is_valid_xml_with_counts(client, checked):
    _, run_id = checked
    response = client.get(f"/api/runs/{run_id}/report", params={"format": "junit"})
    assert response.headers["content-type"].startswith("application/xml")
    root = ET.fromstring(response.content)  # управляющие символы из вывода вычищены
    suite = root.find("testsuite")
    assert suite is not None
    assert (suite.get("tests"), suite.get("failures"), suite.get("errors")) == ("3", "1", "1")
    cases = suite.findall("testcase")
    assert [c.get("name") for c in cases] == ["один", "два | три", "таймаут"]
    assert cases[0].find("failure") is None
    failure = cases[1].find("failure")
    assert failure is not None and "+-9" in (failure.text or "")
    assert cases[2].find("error") is not None


def test_report_errors(client, checked):
    _, run_id = checked
    assert client.get("/api/runs/999/report").status_code == 404
    assert client.get(f"/api/runs/{run_id}/report", params={"format": "pdf"}).status_code == 400


def test_project_report_summarises_version_scenarios_and_runs(client, checked):
    project, run_id = checked
    md = client.get(f"/api/projects/{project['id']}/export/report")
    assert md.status_code == 200
    assert "report-v1.md" in md.headers["content-disposition"]
    text = md.text
    assert text.startswith("# Сводный отчёт: отчёт")
    assert "Проверка поведения: отличается" in text
    assert "| два \\| три | ✗ FAIL |" in text
    assert "## Сценарии (1)" in text
    assert f"| {run_id} | test | done |" in text

    data = client.get(
        f"/api/projects/{project['id']}/export/report", params={"format": "json"}
    ).json()
    assert data["behavior"]["id"] == run_id
    assert [s["name"] for s in data["scenarios"]["scenarios"]] == ["один"]
    assert data["version"]["gate_status"] == "failed"


def test_project_report_for_an_unchecked_version(client, make_project):
    project = make_project()
    text = client.get(f"/api/projects/{project['id']}/export/report").text
    assert "Проверка этой версии не запускалась." in text
    assert "Запусков не было." in text
    assert (
        client.get(
            f"/api/projects/{project['id']}/export/report", params={"version_id": 99}
        ).status_code
        == 404
    )


def test_bundle_contains_sources_reports_and_scenarios(client, checked):
    project, _ = checked
    response = client.get(f"/api/projects/{project['id']}/export/bundle")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.namelist() == [
            "reports/junit.xml",
            "reports/report.json",
            "reports/report.md",
            "scenarios/scenarios.json",
            "src/Main.java",
        ]
        scenarios = json.loads(archive.read("scenarios/scenarios.json"))
        assert [s["name"] for s in scenarios["scenarios"]] == ["один"]
        ET.fromstring(archive.read("reports/junit.xml"))
        assert archive.read("src/Main.java").decode("utf-8").startswith("public class Main")
    assert client.get(f"/api/projects/{project['id']}/export/bundle").content == response.content


def test_bundle_without_checks_has_no_junit(client, make_project):
    project = make_project()
    response = client.get(f"/api/projects/{project['id']}/export/bundle")
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert "reports/junit.xml" not in archive.namelist()
        assert "reports/report.md" in archive.namelist()
