"""Проекты, импорт, версии и файлы (docs/08-api.md § 2–3)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel, FileDiff, FileEntry, SyntaxIssue

GateStatus = Literal["unknown", "passed", "failed"]
VersionStatus = Literal["active", "candidate", "rejected"]
VersionOrigin = Literal[
    "upload",
    "code_edit",
    "graph_op",
    "autofix",
    "optimize",
    "extract_method",
    "decompose",
    "revert",
]


class SampleInfo(ApiModel):
    id: str
    name: str
    description: str
    lines: int


class SampleList(ApiModel):
    samples: list[SampleInfo]


class ProjectFileIn(BaseModel):
    path: str
    content: str


class ProjectCreateFiles(BaseModel):
    """Вставка текста: ``application/json`` с файлами."""

    name: str
    files: list[ProjectFileIn]


class ProjectCreateSample(BaseModel):
    """Встроенный пример: ``application/json`` с ``sample_id``."""

    name: str | None = None
    sample_id: str


ProjectCreateJson = Annotated[ProjectCreateFiles | ProjectCreateSample, Field()]

# Тот же эндпоинт принимает ``multipart/form-data``: ``name``, ``files[]`` (.java) или ``archive`` (.zip).
PROJECT_CREATE_MULTIPART = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "files": {"type": "array", "items": {"type": "string", "format": "binary"}},
        "archive": {"type": "string", "format": "binary"},
    },
    "required": ["name"],
}


class ProjectCreated(ApiModel):
    id: int
    name: str
    head_version_id: int
    original_version_id: int
    main_class: str | None = None
    main_class_candidates: list[str]
    syntax_errors: list[SyntaxIssue]
    files: list[FileEntry]


class ProjectSettings(ApiModel):
    run_timeout_s: int
    compile_timeout_s: int
    output_limit_bytes: int
    jvm_xmx: str
    locale: str  # например "en_US": влияет на String.format
    timezone: str
    rule_thresholds: dict[str, float]
    gate_min_scenarios: int
    gate_min_coverage: float


class ProjectSettingsPatch(BaseModel):
    run_timeout_s: int | None = Field(default=None, ge=1, le=60)
    compile_timeout_s: int | None = Field(default=None, ge=1, le=120)
    output_limit_bytes: int | None = Field(default=None, ge=1024)
    jvm_xmx: str | None = None
    locale: str | None = None
    timezone: str | None = None
    rule_thresholds: dict[str, float] | None = None
    gate_min_scenarios: int | None = Field(default=None, ge=0)
    gate_min_coverage: float | None = Field(default=None, ge=0, le=1)


class GateSummary(ApiModel):
    """Статус поведения HEAD: «✓ совпадает (12/12)», «✗ отличается (2)», «? не проверено»."""

    status: GateStatus
    passed: int | None = None
    total: int | None = None
    coverage: float | None = None
    run_id: int | None = None


class ProjectSummary(ApiModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    head_version_id: int
    main_class: str | None = None
    files_count: int


class ProjectList(ApiModel):
    projects: list[ProjectSummary]


class ProjectDetail(ApiModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    main_class: str | None = None
    main_class_candidates: list[str]
    head_version_id: int
    original_version_id: int
    baseline_version_id: int | None = None
    settings: ProjectSettings
    gate: GateSummary


class ProjectPatch(BaseModel):
    name: str | None = None
    main_class: str | None = None
    settings: ProjectSettingsPatch | None = None


class VersionInfo(ApiModel):
    id: int
    number: int
    parent_id: int | None = None
    origin: VersionOrigin
    description: str
    created_at: datetime
    gate_status: GateStatus
    status: VersionStatus
    content_hash: str


class VersionList(ApiModel):
    head_version_id: int
    versions: list[VersionInfo]


class VersionDetail(ApiModel):
    version: VersionInfo
    files: list[FileEntry]


class VersionChange(ApiModel):
    """Результат действия, создавшего версию или переместившего HEAD."""

    version: VersionInfo
    head_version_id: int
    changed_files: list[str]
    syntax_errors: list[SyntaxIssue]
    collapsed: bool = False  # правка схлопнута с предыдущей code_edit


class FileList(ApiModel):
    version_id: int
    files: list[FileEntry]


class FileContent(ApiModel):
    path: str
    version_id: int
    content: str
    syntax_errors: list[SyntaxIssue]


class FileSave(BaseModel):
    base_version_id: int
    content: str


class FileCreate(BaseModel):
    path: str
    content: str = ""


class VersionDiff(ApiModel):
    from_version_id: int
    to_version_id: int
    files: list[FileDiff]
