"""Дополнения OpenAPI, которые FastAPI не выводит сам.

``POST /projects`` принимает ``multipart/form-data`` или JSON двух видов; тело разбирается вручную
(``Request``), поэтому схемы JSON-вариантов добавляются в ``components`` здесь, а в маршруте
ссылаются на них через ``openapi_extra``.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from app.schemas.project import PROJECT_CREATE_MULTIPART, ProjectCreateFiles, ProjectCreateSample

EXTRA_MODELS: tuple[type[BaseModel], ...] = (ProjectCreateFiles, ProjectCreateSample)

PROJECT_CREATE_BODY: dict[str, Any] = {
    "required": True,
    "content": {
        "application/json": {
            "schema": {
                "oneOf": [
                    {"$ref": "#/components/schemas/ProjectCreateFiles"},
                    {"$ref": "#/components/schemas/ProjectCreateSample"},
                ]
            }
        },
        "multipart/form-data": {"schema": PROJECT_CREATE_MULTIPART},
    },
}


def install_openapi_extras(app: FastAPI) -> None:
    original = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = original()
        definitions = schema.setdefault("components", {}).setdefault("schemas", {})
        for model in EXTRA_MODELS:
            body = model.model_json_schema(ref_template="#/components/schemas/{model}")
            definitions.update(body.pop("$defs", {}))
            definitions[model.__name__] = body
        return schema

    app.openapi = openapi  # type: ignore[method-assign]
