"""Where run jobs go: inline (tests), a thread in the API process, or Redis with arq.

All three call the same `run_job`, so behavior does not depend on the queue.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Literal, Protocol

from arq import create_pool
from arq.connections import RedisSettings

from joinpilot.config import Settings

logger = logging.getLogger(__name__)
JobName = Literal["start_run", "resume_run"]


class JobQueue(Protocol):
    """Accepts a job to run later (or now)."""

    def submit(self, name: JobName, run_id: str) -> None:
        """Queue one job for a run."""
        ...


def run_job(settings: Settings, name: JobName, run_id: str) -> None:
    """Execute one job: move the run forward from its saved state (start or resume).

    Errors are logged here as well, because a thread pool would otherwise drop them.
    """
    from joinpilot.services.runs import RunService

    try:
        service = RunService(settings, InlineJobQueue(settings))
        if name == "start_run":
            service.execute(run_id)
        else:
            service.resume(run_id)
    except Exception:
        logger.exception("job %s for run %s failed", name, run_id)
        raise


class InlineJobQueue:
    """Runs the job immediately in the caller's thread (tests and scripts)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def submit(self, name: JobName, run_id: str) -> None:
        """Run the job now."""
        run_job(self.settings, name, run_id)


class ThreadJobQueue:
    """Runs jobs in a small thread pool inside the API process (no Redis needed)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.pool = ThreadPoolExecutor(
            max_workers=settings.jobs_max_concurrent, thread_name_prefix="joinpilot-job"
        )

    def submit(self, name: JobName, run_id: str) -> None:
        """Hand the job to a background thread."""
        self.pool.submit(run_job, self.settings, name, run_id)

    def close(self) -> None:
        """Wait for running jobs and stop the pool (on app shutdown)."""
        self.pool.shutdown(wait=True, cancel_futures=False)


class ArqJobQueue:
    """Puts jobs on Redis for the arq worker, each under its own job id.

    arq drops a job whose id it has seen in the last hour, so a fixed id per run step
    silently lost a second resume (after an approval that was undone and sent again)
    and left the run stuck. Duplicate jobs are harmless: `RunService.advance` does
    nothing when there is nothing to do.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.redis_url:
            raise ValueError("JOBS_MODE=arq needs REDIS_URL")
        self.redis_url = settings.redis_url

    def submit(self, name: JobName, run_id: str) -> None:
        """Enqueue the job (called from a worker thread, so it runs its own event loop)."""

        async def enqueue() -> None:
            pool = await create_pool(RedisSettings.from_dsn(self.redis_url))
            try:
                job_id = f"{name}:{run_id}:{uuid.uuid4().hex[:12]}"
                await pool.enqueue_job(name, run_id, _job_id=job_id)
            finally:
                await pool.aclose()

        asyncio.run(enqueue())


def make_job_queue(settings: Settings) -> JobQueue:
    """The configured queue: inline, a thread pool, or Redis with arq."""
    if settings.jobs_mode == "inline":
        return InlineJobQueue(settings)
    if settings.jobs_mode == "arq":
        return ArqJobQueue(settings)
    return ThreadJobQueue(settings)
