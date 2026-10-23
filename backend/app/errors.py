"""Единый формат ошибок API: ``{"error": {"code", "message", "details"}}`` (docs/08-api.md § 1)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import request_id_var

log = logging.getLogger("app.errors")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(Exception):
    """Ожидаемая ошибка API с кодом из docs/08-api.md."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def not_found(message: str, **details: Any) -> ApiError:
    return ApiError(404, "NOT_FOUND", message, details or None)


def bad_request(message: str, **details: Any) -> ApiError:
    return ApiError(400, "BAD_REQUEST", message, details or None)


def version_conflict(message: str, **details: Any) -> ApiError:
    return ApiError(409, "VERSION_CONFLICT", message, details or None)


def _response(status_code: int, code: str, message: str, details: dict[str, Any] | None = None):
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(status_code=status_code, content=body.model_dump(exclude_none=True))


_HTTP_CODES = {400: "BAD_REQUEST", 404: "NOT_FOUND", 405: "BAD_REQUEST", 413: "PAYLOAD_TOO_LARGE"}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return _response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        errors = [{"loc": [str(p) for p in e["loc"]], "msg": e["msg"]} for e in exc.errors()]
        return _response(400, "BAD_REQUEST", "Неверные параметры запроса", {"errors": errors})

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = _HTTP_CODES.get(
            exc.status_code, "BAD_REQUEST" if exc.status_code < 500 else "INTERNAL"
        )
        return _response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception):
        request_id = request_id_var.get()
        log.exception("unhandled error", extra={"request_id": request_id})
        return _response(500, "INTERNAL", "Внутренняя ошибка сервера", {"request_id": request_id})
