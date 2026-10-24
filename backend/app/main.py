"""Точка входа FastAPI: ``uvicorn app.main:app``."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

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
from app.config import Settings, get_settings
from app.db.session import get_engine, init_db
from app.errors import register_error_handlers
from app.jobs.registry import all_handlers
from app.jobs.run_manager import RunManager
from app.logging_config import RequestIdMiddleware, configure_logging
from app.openapi import install_openapi_extras
from app.services.seeding import seed_demo


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.ensure_dirs()
    init_db()
    manager = RunManager(settings, all_handlers())
    app.state.run_manager = manager
    log = logging.getLogger("app")
    interrupted = await asyncio.to_thread(manager.recover)
    if interrupted:
        log.warning("marked interrupted runs", extra={"count": interrupted})
    if settings.seed_demo:
        await asyncio.to_thread(_seed, settings)
    log.info(
        "started", extra={"data_dir": str(settings.data_dir.resolve()), "version": __version__}
    )
    yield
    await manager.shutdown()


def _seed(settings: Settings) -> None:
    with Session(get_engine()) as session:
        seed_demo(session, settings)


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
    install_openapi_extras(app)
    return app


app = create_app()
