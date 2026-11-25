"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from joinpilot import __version__
from joinpilot.api.errors import install_error_handlers
from joinpilot.api.projects import router as projects_router
from joinpilot.api.runs import router as runs_router
from joinpilot.api.schemas import HealthResponse
from joinpilot.config import Settings, get_settings
from joinpilot.db.session import ensure_migrated
from joinpilot.jobs.queue import make_job_queue
from joinpilot.jobs.worker import make_worker


def make_lifespan(settings: Settings) -> Any:
    """Start the in-process arq worker with the app when jobs go through Redis (D-022)."""

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if settings.jobs_mode != "arq":
            yield
            return
        worker = make_worker(settings)
        task = asyncio.create_task(worker.async_run())
        try:
            yield
        finally:
            await worker.close()
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    return lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API with CORS limited to the configured origins."""
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)
    app = FastAPI(title="JoinPilot API", version=__version__, lifespan=make_lifespan(settings))
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    ensure_migrated(settings.db_url)
    app.include_router(projects_router)
    app.include_router(runs_router)
    app.state.jobs = make_job_queue(settings)

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Liveness check used by Docker, the console and uptime pings."""
        return HealthResponse(status="ok", version=__version__)

    return app


app = create_app()
