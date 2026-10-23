"""Точка входа FastAPI: ``uvicorn app.main:app``."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import (
    analysis,
    export,
    graph,
    health,
    ops,
    projects,
    runs,
    scenarios,
    transform,
    versions,
)
from app.config import get_settings
from app.db.session import init_db
from app.errors import register_error_handlers
from app.logging_config import RequestIdMiddleware, configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.ensure_dirs()
    init_db()
    logging.getLogger("app").info(
        "started", extra={"data_dir": str(settings.data_dir.resolve()), "version": __version__}
    )
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Java Blueprints API",
        version=__version__,
        description="Визуальная среда программирования для Java: код ↔ граф, анализ, проверка поведения.",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
        # operationId = имя функции-обработчика: читаемые имена в сгенерированных TS-типах.
        # Имена обработчиков должны быть уникальны во всём приложении.
        generate_unique_id_function=lambda route: route.name,
    )
    settings = get_settings()
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)
    for module in (
        health,
        projects,
        versions,
        graph,
        ops,
        analysis,
        transform,
        scenarios,
        runs,
        export,
    ):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
