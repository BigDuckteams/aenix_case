"""Общие типы контракта: диапазоны кода, диагностики, diff (docs/08-api.md § 1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    """Базовый класс схем ответов.

    Поля со значениями по умолчанию в ответах всегда присутствуют, поэтому в OpenAPI (и в
    сгенерированных TS-типах) они обязательные: frontend не проверяет ``undefined`` у списков.
    """

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class SourceRange(BaseModel):
    """Диапазон кода: строки с 1, колонки в UTF-16 с 1 (как в Monaco; ADR-11)."""

    file: str
    start_line: int = Field(ge=1)
    start_col: int = Field(ge=1)
    end_line: int = Field(ge=1)
    end_col: int = Field(ge=1)


class SyntaxIssue(ApiModel):
    """Синтаксическая ошибка: узел ``ERROR`` или ``MISSING`` из tree-sitter."""

    message: str
    range: SourceRange


class Diagnostic(ApiModel):
    """Диагностика компилятора, привязанная к строке и (по возможности) к узлу графа."""

    file: str
    line: int
    column: int
    end_line: int | None = None
    end_column: int | None = None
    severity: Literal["error", "warning", "note"]
    message: str
    node_id: str | None = None


class FileEntry(ApiModel):
    path: str
    lines: int
    size: int = 0


class FileDiff(ApiModel):
    """Изменение одного файла между версиями или в предпросмотре преобразования."""

    path: str
    status: Literal["added", "removed", "modified"]
    unified: str
    before: str | None = None
    after: str | None = None
