"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from joinpilot import __version__
from joinpilot.api.errors import install_error_handlers
from joinpilot.api.limits import LimitMiddleware
from joinpilot.api.projects import router as projects_router
from joinpilot.api.questions import router as questions_router
from joinpilot.api.runs import router as runs_router
from joinpilot.api.schemas import HealthResponse
from joinpilot.config import Settings, get_settings
from joinpilot.db.session import ensure_migrated
from joinpilot.demo import ensure_demo_project
from joinpilot.jobs.queue import ThreadJobQueue, make_job_queue
from joinpilot.jobs.worker import make_worker
from joinpilot.services.runs import RunService

logger = logging.getLogger(__name__)


async def build_demo(settings: Settings, jobs: Any, stop: threading.Event) -> None:
    """Build the demo project; a failure is logged and leaves the API running."""
    try:
        await asyncio.to_thread(ensure_demo_project, settings, jobs, stop)
    except Exception:
        logger.exception("could not build the demo project")


def make_lifespan(settings: Settings) -> Any:
    """On startup: migrate, re-queue runs a restart interrupted (thread mode), and start the
    in-process arq worker when jobs go through Redis (D-022). On shutdown: stop them."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await asyncio.to_thread(ensure_migrated, settings.db_url)
        jobs = app.state.jobs
        if settings.jobs_mode == "thread":
            recovered = await asyncio.to_thread(RunService(settings, jobs).recover)
            if recovered:
                logger.info("re-queued %d interrupted runs", recovered)
        worker = make_worker(settings) if settings.jobs_mode == "arq" else None
        task = asyncio.create_task(worker.async_run()) if worker else None
        # Built in the background, so health checks pass while the sample loads.
        stop_demo = threading.Event()
        demo = (
            asyncio.create_task(build_demo(settings, jobs, stop_demo))
            if settings.demo_mode
            else None
        )
        try:
            yield
        finally:
            if demo:
                stop_demo.set()  # the build thread stops waiting within half a second
                with suppress(asyncio.CancelledError):
                    await demo
            if worker and task:
                await worker.close()
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            if isinstance(jobs, ThreadJobQueue):
                await asyncio.to_thread(jobs.close)

    return lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API with CORS limited to the configured origins."""
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)
    app = FastAPI(title="JoinPilot API", version=__version__, lifespan=make_lifespan(settings))
    app.state.settings = settings
    # Limits run inside CORS, so even a refusal carries the CORS headers the console needs.
    app.add_middleware(LimitMiddleware, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(projects_router)
    app.include_router(runs_router)
    app.include_router(questions_router)
    app.state.jobs = make_job_queue(settings)

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Liveness check used by Docker, the console and uptime pings."""
        return HealthResponse(status="ok", version=__version__)

    return app


app = create_app()
