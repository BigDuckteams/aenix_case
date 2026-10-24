"""SQLModel-модели (docs/02-architecture.md § 5.1).

Ссылки между ``project`` и ``version`` (head/original/baseline, parent) — обычные целые без
внешних ключей: иначе возникает циклическая зависимость таблиц при ``create_all``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class VersionOrigin(StrEnum):
    UPLOAD = "upload"
    CODE_EDIT = "code_edit"
    GRAPH_OP = "graph_op"
    AUTOFIX = "autofix"
    OPTIMIZE = "optimize"
    EXTRACT_METHOD = "extract_method"
    DECOMPOSE = "decompose"
    REVERT = "revert"


class VersionStatus(StrEnum):
    ACTIVE = "active"
    CANDIDATE = "candidate"
    REJECTED = "rejected"


class GateStatus(StrEnum):
    UNKNOWN = "unknown"
    PASSED = "passed"
    FAILED = "failed"


class ScenarioSource(StrEnum):
    MANUAL = "manual"
    IMPORTED = "imported"
    GENERATED = "generated"
    SCALED = "scaled"


class Stability(StrEnum):
    STABLE = "stable"
    MASKED = "masked"
    NONDETERMINISTIC = "nondeterministic"


class RunKind(StrEnum):
    RUN = "run"
    TEST = "test"
    GATE = "gate"
    BASELINE = "baseline"
    GENERATE = "generate"
    BENCHMARK = "benchmark"
    TRACE = "trace"
    VERIFY = "verify"
    OPTIMIZE = "optimize"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ERROR = "error"


class Project(SQLModel, table=True):
    __tablename__ = "project"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    main_class: str | None = None
    original_version_id: int | None = None
    head_version_id: int | None = None
    baseline_version_id: int | None = None
    settings: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Version(SQLModel, table=True):
    __tablename__ = "version"
    __table_args__ = (UniqueConstraint("project_id", "number"),)

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    number: int
    parent_id: int | None = None
    origin: str = VersionOrigin.UPLOAD.value
    description: str = ""
    content_hash: str = Field(index=True)
    status: str = VersionStatus.ACTIVE.value
    gate_status: str = GateStatus.UNKNOWN.value
    gate_run_id: int | None = None
    meta: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class SourceFile(SQLModel, table=True):
    __tablename__ = "source_file"
    __table_args__ = (UniqueConstraint("version_id", "path"),)

    id: int | None = Field(default=None, primary_key=True)
    version_id: int = Field(foreign_key="version.id", index=True)
    path: str
    content: str
    sha256: str


class Scenario(SQLModel, table=True):
    __tablename__ = "scenario"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    name: str
    description: str = ""
    stdin: str = ""
    args: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    source: str = ScenarioSource.MANUAL.value
    size_factor: int | None = None
    enabled: bool = True
    stability: str = Stability.STABLE.value
    masks: list[dict[str, str]] = Field(default_factory=list, sa_column=Column(JSON))
    expected_stdout: str | None = None  # ожидание организаторов (docs/07 § 4.3)
    expected_exit_code: int | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Baseline(SQLModel, table=True):
    __tablename__ = "baseline"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    scenario_id: int = Field(foreign_key="scenario.id", index=True)
    version_id: int
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    exception: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    duration_ms: int | None = None
    coverage: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class Run(SQLModel, table=True):
    __tablename__ = "run"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    version_id: int | None = None
    kind: str
    status: str = RunStatus.QUEUED.value
    started_at: datetime | None = None
    finished_at: datetime | None = None
    summary: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class RunItem(SQLModel, table=True):
    __tablename__ = "run_item"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    scenario_id: int | None = Field(default=None, foreign_key="scenario.id")
    name: str = ""
    status: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    duration_ms: int | None = None
    baseline_ms: int | None = None
    diff: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    hits: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    op_count: int | None = None
