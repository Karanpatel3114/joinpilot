"""The arq worker: run jobs from Redis.

By default it runs inside the API process (started by the app's lifespan), because
one process owns each project's DuckDB file (D-016). It can also run on its own:
    uv run arq joinpilot.jobs.worker.WorkerSettings
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from arq.connections import RedisSettings
from arq.worker import Worker

from joinpilot.config import Settings, get_settings
from joinpilot.jobs.queue import run_job


async def start_run(ctx: dict[str, Any], run_id: str) -> None:
    """Job: run the graph until the approval pause."""
    await asyncio.to_thread(run_job, ctx["settings"], "start_run", run_id)


async def resume_run(ctx: dict[str, Any], run_id: str) -> None:
    """Job: resume a run after approval."""
    await asyncio.to_thread(run_job, ctx["settings"], "resume_run", run_id)


def make_worker(settings: Settings) -> Worker:
    """A worker for the in-process mode (signals stay with the web server)."""
    return Worker(
        functions=[start_run, resume_run],
        redis_settings=RedisSettings.from_dsn(settings.redis_url),
        ctx={"settings": settings},
        handle_signals=False,
        max_jobs=settings.jobs_max_concurrent,
        job_timeout=settings.jobs_timeout_seconds,
        keep_result=3600,
    )


async def _startup(ctx: dict[str, Any]) -> None:
    ctx["settings"] = get_settings()


class WorkerSettings:
    """Settings for the standalone `arq` command."""

    functions: ClassVar[list[Any]] = [start_run, resume_run]
    on_startup = _startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url or "redis://localhost:6379")
    max_jobs = get_settings().jobs_max_concurrent
    job_timeout = get_settings().jobs_timeout_seconds
