"""Where run jobs go: inline (tests), a thread in the API process (local), or Redis (M5.6).

All three call the same `run_job`, so behavior does not depend on the queue.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Literal, Protocol

from joinpilot.config import Settings

JobName = Literal["start_run", "resume_run"]


class JobQueue(Protocol):
    """Accepts a job to run later (or now)."""

    def submit(self, name: JobName, run_id: str) -> None:
        """Queue one job for a run."""
        ...


def run_job(settings: Settings, name: JobName, run_id: str) -> None:
    """Execute one job: start a run up to the approval pause, or resume it after approval."""
    from joinpilot.services.runs import RunService

    service = RunService(settings, InlineJobQueue(settings))
    if name == "start_run":
        service.execute(run_id)
    else:
        service.resume(run_id)


class InlineJobQueue:
    """Runs the job immediately in the caller's thread (tests and scripts)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def submit(self, name: JobName, run_id: str) -> None:
        """Run the job now."""
        run_job(self.settings, name, run_id)


class ThreadJobQueue:
    """Runs jobs in a small thread pool inside the API process (no Redis needed)."""

    def __init__(self, settings: Settings, workers: int = 2) -> None:
        self.settings = settings
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="joinpilot-job")

    def submit(self, name: JobName, run_id: str) -> None:
        """Hand the job to a background thread."""
        self.pool.submit(run_job, self.settings, name, run_id)


def make_job_queue(settings: Settings) -> JobQueue:
    """The configured queue: inline, or a thread pool (Redis arrives in M5.6)."""
    if settings.jobs_mode == "inline":
        return InlineJobQueue(settings)
    return ThreadJobQueue(settings)
