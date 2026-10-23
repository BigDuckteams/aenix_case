from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.db.models import (
    Baseline,
    Project,
    Run,
    RunItem,
    Scenario,
    SourceFile,
    Version,
)


def test_sqlite_uses_wal_and_foreign_keys(session):
    assert session.exec(text("PRAGMA journal_mode")).scalar() == "wal"
    assert session.exec(text("PRAGMA foreign_keys")).scalar() == 1


def test_full_object_graph_roundtrip(session):
    project = Project(name="demo", settings={"locale": "ru"})
    session.add(project)
    session.commit()

    version = Version(project_id=project.id, number=1, content_hash="abc", meta={"ops": []})
    session.add(version)
    session.commit()
    project.original_version_id = project.head_version_id = version.id
    session.add(
        SourceFile(version_id=version.id, path="Main.java", content="class Main {}", sha256="x")
    )

    scenario = Scenario(project_id=project.id, name="empty", stdin="Привет\n", args=["-v"])
    session.add(scenario)
    session.commit()

    session.add(
        Baseline(
            project_id=project.id,
            scenario_id=scenario.id,
            version_id=version.id,
            stdout="ok",
            exception={"type": "java.lang.IllegalStateException", "message": "boom"},
        )
    )
    run = Run(project_id=project.id, version_id=version.id, kind="test")
    session.add(run)
    session.commit()
    session.add(RunItem(run_id=run.id, scenario_id=scenario.id, status="PASS", hits={"1": 3}))
    session.commit()

    session.expire_all()
    loaded = session.exec(select(Scenario)).one()
    assert loaded.stdin == "Привет\n"
    assert loaded.args == ["-v"]
    assert session.exec(select(Project)).one().settings == {"locale": "ru"}
    assert session.exec(select(Baseline)).one().exception["message"] == "boom"
    assert session.exec(select(RunItem)).one().hits == {"1": 3}


def test_foreign_keys_are_enforced(session):
    session.add(Version(project_id=999, number=1, content_hash="h"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_version_numbers_are_unique_per_project(session):
    project = Project(name="p")
    session.add(project)
    session.commit()
    session.add(Version(project_id=project.id, number=1, content_hash="a"))
    session.commit()
    session.add(Version(project_id=project.id, number=1, content_hash="b"))
    with pytest.raises(IntegrityError):
        session.commit()
