"""Общие части роутеров."""

from __future__ import annotations

from typing import Any

from sse_starlette.sse import EventSourceResponse

from app.errors import ErrorResponse

# Любая ошибка (4xx/5xx) приходит в одном формате (docs/08-api.md § 1). ``default`` также
# заменяет автоматический ответ 422 FastAPI: ошибки валидации у нас возвращаются как 400.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    "default": {"model": ErrorResponse, "description": "Ошибка в едином формате"},
}

# Для маршрутов с не-JSON ответом (SSE): ошибки до начала потока всё равно приходят как JSON.
ERROR_JSON_RESPONSE: dict[int | str, dict[str, Any]] = {
    "default": {
        "description": "Ошибка в едином формате",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
    },
}


class SseResponse(EventSourceResponse):
    """``EventSourceResponse`` с media type на уровне класса: по нему FastAPI описывает ответ в OpenAPI."""

    media_type = "text/event-stream"
