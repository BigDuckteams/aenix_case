"""Запуски, SSE и сборка (docs/08-api.md § 8.2–8.3, § 9). Заглушки контракта (S1.1):
реализация — этапы S3 (сборка, запуск) и S6 (gate, эталон, отчёты)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Response

from app.api.common import ERROR_JSON_RESPONSE, ERROR_RESPONSES, SseResponse
from app.errors import not_implemented
from app.schemas.verify import (
    BuildRequest,
    BuildResult,
    RunEvent,
    RunInfo,
    RunList,
    RunRef,
    RunRequest,
)

router = APIRouter(tags=["runs"], responses=ERROR_RESPONSES)

_REPORT_TYPES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "Отчёт в выбранном формате",
        "content": {
            "application/json": {"schema": {"type": "object"}},
            "text/markdown": {"schema": {"type": "string"}},
            "application/xml": {"schema": {"type": "string"}},
        },
    }
}


@router.post(
    "/projects/{project_id}/runs",
    status_code=202,
    summary="Запустить задачу",
    description=(
        "`kind`: `run`, `trace`, `baseline`, `test`, `gate`, `generate`, `benchmark`, `verify`. "
        "Ответ `202`; ход выполнения — `GET /runs/{run_id}/events`. `429 BUSY` — слишком много "
        "параллельных запусков."
    ),
)
def create_run(project_id: int, payload: RunRequest) -> RunRef:
    raise not_implemented("S3")


@router.get("/projects/{project_id}/runs", summary="История запусков")
def list_runs(project_id: int) -> RunList:
    raise not_implemented("S3")


@router.get("/runs/{run_id}", summary="Статус и итог запуска")
def get_run(run_id: int) -> RunInfo:
    raise not_implemented("S3")


@router.get(
    "/runs/{run_id}/events",
    summary="SSE-поток запуска",
    description=(
        "`text/event-stream`: события `status`, `log`, `gate`, `item`, `step`, `progress`, "
        "`result`, `error`, `done` (каждое — `event:` + `data:` JSON). Поздние подписчики "
        "получают replay с начала; heartbeat-комментарий каждые 15 секунд."
    ),
    response_class=SseResponse,
    responses={
        200: {"model": RunEvent, "description": "Поток событий запуска"},
        **ERROR_JSON_RESPONSE,
    },
)
def run_events(run_id: int) -> Any:
    raise not_implemented("S3")


@router.post("/runs/{run_id}/cancel", summary="Отменить запуск")
def cancel_run(run_id: int) -> RunInfo:
    raise not_implemented("S3")


@router.get(
    "/runs/{run_id}/report",
    summary="Отчёт запуска для скачивания",
    response_class=Response,
    responses=_REPORT_TYPES,
)
def get_run_report(run_id: int, format: Literal["json", "md", "junit"] = "json") -> Any:
    raise not_implemented("S6")


@router.post(
    "/projects/{project_id}/build",
    summary="Синхронная сборка версии",
    description="Компиляция HEAD или `version_id`; кеш по хешу. Для быстрых ошибок в маркерах Monaco.",
)
def build_project(project_id: int, payload: BuildRequest) -> BuildResult:
    raise not_implemented("S3")
