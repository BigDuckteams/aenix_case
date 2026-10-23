"""Сценарии, запуски, сборка и SSE-события (docs/08-api.md § 8–9, docs/07-behavior-verification.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel, Diagnostic

ScenarioSource = Literal["manual", "imported", "generated", "scaled"]
Stability = Literal["stable", "masked", "nondeterministic"]
BaselineState = Literal["none", "recorded", "stale"]

RunKind = Literal["run", "trace", "baseline", "test", "gate", "generate", "benchmark", "verify"]
RunStatus = Literal["queued", "running", "done", "failed", "cancelled", "error"]
Verdict = Literal["PASS", "FAIL", "ERROR", "TIMEOUT"]


class Mask(BaseModel):
    """Маска нестабильного фрагмента: регулярное выражение → токен (``\\d+ мс`` → ``<MS>``)."""

    pattern: str
    replacement: str


class ScenarioCreate(BaseModel):
    name: str
    description: str = ""
    stdin: str = ""
    args: list[str] = []


class ScenarioUpdate(BaseModel):
    """Изменение сценария сбрасывает его эталон."""

    name: str | None = None
    description: str | None = None
    stdin: str | None = None
    args: list[str] | None = None
    enabled: bool | None = None
    masks: list[Mask] | None = None


class BaselineStatus(ApiModel):
    state: BaselineState
    version_id: int | None = None
    duration_ms: int | None = None


class Scenario(ApiModel):
    id: int
    name: str
    description: str
    stdin: str
    args: list[str]
    source: ScenarioSource
    size_factor: int | None = None
    enabled: bool
    stability: Stability
    masks: list[Mask]
    baseline: BaselineStatus
    created_at: datetime


class ScenarioList(ApiModel):
    scenarios: list[Scenario]


class ScenarioImportItem(BaseModel):
    """Формат импорта/экспорта: ``expected_*`` — ожидание организаторов (07 § 4.3)."""

    name: str
    description: str = ""
    stdin: str = ""
    args: list[str] = []
    expected_stdout: str | None = None
    expected_exit_code: int | None = None


class ScenarioImport(BaseModel):
    scenarios: list[ScenarioImportItem]


class ScenarioExportItem(ApiModel):
    name: str
    description: str
    stdin: str
    args: list[str]
    expected_stdout: str | None = None
    expected_exit_code: int | None = None


class ScenarioExport(ApiModel):
    scenarios: list[ScenarioExportItem]


class ScenarioImportResult(ApiModel):
    imported: int
    scenario_ids: list[int]
    warnings: list[str]


class InputSchemaNode(ApiModel):
    """Узел выведенной схемы ввода: токен, строка, повтор, цикл команд."""

    kind: Literal["token", "line", "repeat", "command_loop"]
    type: Literal["int", "long", "double", "string", "word", "line"] | None = None
    source: str | None = None  # «nextInt@L12»
    count_ref: str | None = None  # для repeat: имя ранее прочитанной переменной
    labels: list[str] = []  # для command_loop: add/remove/list/quit
    children: list[InputSchemaNode] = []


class InputSchema(ApiModel):
    inferred: bool  # False — схема не выведена, используется запасной путь
    root: list[InputSchemaNode]


InputSchemaNode.model_rebuild()


class RunRequest(BaseModel):
    """Запуск: поля зависят от ``kind`` (07 § 8.2)."""

    kind: RunKind
    version_id: int | None = None
    scenario_ids: list[int] | None = None
    stdin: str | None = None  # kind=run|trace
    args: list[str] | None = None  # kind=run|trace
    sizes: list[int] | None = None  # kind=benchmark
    finding_id: str | None = None  # kind=verify


class RunRef(ApiModel):
    """Ссылка на фоновый запуск: дальше — ``GET /runs/{id}`` и SSE."""

    run_id: int
    status: Literal["queued"] = "queued"


class TextChange(ApiModel):
    expected: str
    actual: str
    unified: str


class ExitCodeChange(ApiModel):
    expected: int | None = None
    actual: int | None = None


class ExceptionChange(ApiModel):
    expected: str | None = None  # «Тип: сообщение»
    actual: str | None = None


class BehaviorDiff(ApiModel):
    """Чем фактическое поведение отличается от эталона."""

    stdout: TextChange | None = None
    stderr: TextChange | None = None
    exit_code: ExitCodeChange | None = None
    exception: ExceptionChange | None = None


class RunItem(ApiModel):
    scenario_id: int | None = None
    name: str
    verdict: Verdict
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    duration_ms: int
    baseline_ms: int | None = None
    diff: BehaviorDiff | None = None
    hits: dict[str, int] | None = None  # трассировка: node_id → число выполнений


class RunSummary(ApiModel):
    passed: int | None = None
    total: int | None = None
    coverage: float | None = None
    version_status: Literal["passed", "failed", "unknown"] | None = None
    message: str | None = None
    data: dict[str, Any] | None = None  # benchmark / trace / generate


class RunInfo(ApiModel):
    id: int
    kind: RunKind
    status: RunStatus
    version_id: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    summary: RunSummary
    items: list[RunItem] = []


class RunList(ApiModel):
    runs: list[RunInfo]


class BuildRequest(BaseModel):
    version_id: int | None = None


class BuildResult(ApiModel):
    ok: bool
    diagnostics: list[Diagnostic]
    duration_ms: int
    cached: bool


# --- SSE (07 § 9): каждое событие — ``event:`` + ``data:``; модели описывают и то и другое ---


class StatusData(ApiModel):
    status: RunStatus


class LogData(ApiModel):
    stream: Literal["build", "stdout", "stderr", "info"]
    text: str


class GateData(ApiModel):
    stage: Literal["syntax", "compile", "scenarios", "coverage"]
    status: Literal["running", "passed", "failed"]
    details: str | None = None


class ItemData(ApiModel):
    scenario_id: int | None = None
    name: str
    verdict: Verdict
    duration_ms: int
    baseline_ms: int | None = None
    diff: BehaviorDiff | None = None


class StepData(ApiModel):
    step_id: str
    title: str
    status: Literal["applying", "passed", "skipped"]
    reason: str | None = None


class ProgressData(ApiModel):
    done: int
    total: int


class ResultData(ApiModel):
    summary: RunSummary


class ErrorData(ApiModel):
    code: str
    message: str


class DoneData(ApiModel):
    pass


class StatusEvent(ApiModel):
    event: Literal["status"] = "status"
    data: StatusData


class LogEvent(ApiModel):
    event: Literal["log"] = "log"
    data: LogData


class GateEvent(ApiModel):
    event: Literal["gate"] = "gate"
    data: GateData


class ItemEvent(ApiModel):
    event: Literal["item"] = "item"
    data: ItemData


class StepEvent(ApiModel):
    event: Literal["step"] = "step"
    data: StepData


class ProgressEvent(ApiModel):
    event: Literal["progress"] = "progress"
    data: ProgressData


class ResultEvent(ApiModel):
    event: Literal["result"] = "result"
    data: ResultData


class ErrorEvent(ApiModel):
    event: Literal["error"] = "error"
    data: ErrorData


class DoneEvent(ApiModel):
    event: Literal["done"] = "done"
    data: DoneData


RunEvent = Annotated[
    StatusEvent
    | LogEvent
    | GateEvent
    | ItemEvent
    | StepEvent
    | ProgressEvent
    | ResultEvent
    | ErrorEvent
    | DoneEvent,
    Field(discriminator="event"),
]
