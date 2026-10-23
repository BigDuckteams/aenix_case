from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    javac: str | None = None
    java: str | None = None
    db: Literal["ok", "error"]
    problems: list[str] = []
