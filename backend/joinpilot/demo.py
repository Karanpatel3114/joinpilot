"""Demo mode: a ready, read-only sample project for visitors of the public demo.

With `DEMO_MODE=true` the API builds it in the background at startup: it loads the
synthetic ERP sample into the shared `demo` workspace, runs the agent on an example
requirement, approves the joins the scorer recommends, and lets the run build its
views, checks and dashboard. It is built in a hidden staging workspace and moved into
`demo` only once the run has completed, so visitors never see it half built. Free hosts
wipe their disk on restart, so this runs on every start; a finished demo is kept (D-037).
"""

from __future__ import annotations

import logging
import threading
import time

from joinpilot.agent.approval import Decision
from joinpilot.config import Settings
from joinpilot.jobs.queue import JobQueue
from joinpilot.services.projects import ProjectService
from joinpilot.services.runs import RunService
from joinpilot.workspaces import DEMO, DEMO_STAGING

logger = logging.getLogger(__name__)

DEMO_NAME = "Sample ERP (read-only)"
DEMO_SAMPLE = "erp_s1_sap"
DEMO_REQUIREMENT = (
    "Open receivables by customer and aging bucket, plus 2026 revenue by product group."
)
SETTLED = frozenset({"awaiting_approval", "completed", "failed"})


def ensure_demo_project(
    settings: Settings, jobs: JobQueue, stop: threading.Event | None = None
) -> str | None:
    """The demo project's id, building it first when the demo workspace is empty.

    Returns None when the build did not complete (or `stop` was set); the half-built
    project then stays hidden in the staging workspace.
    """
    stop = stop or threading.Event()
    projects = ProjectService(settings)
    existing = projects.list_projects(DEMO)
    if existing:
        return existing[0].id
    started = time.monotonic()
    project = projects.create(DEMO_NAME, DEMO_STAGING)
    projects.add_sample(project.id, DEMO_SAMPLE)
    runs = RunService(settings, jobs)
    run = runs.start(project.id, DEMO_REQUIREMENT)
    timeout = settings.jobs_timeout_seconds
    status = wait_for(runs, run.run_id, SETTLED, timeout, stop)
    if status == "awaiting_approval":
        decisions = [
            Decision(edge_id=p["edge_id"], action="approve" if p["recommended"] else "reject")
            for p in runs.proposals(run.run_id)
        ]
        runs.approve(run.run_id, decisions)
        status = wait_for(runs, run.run_id, {"completed", "failed"}, timeout, stop)
    seconds = time.monotonic() - started
    if status != "completed":
        logger.warning(
            "demo project not built: run %s ended %s after %.1f s", run.run_id, status, seconds
        )
        return None
    projects.store.move(project.id, DEMO)
    logger.info("demo project %s built: run %s in %.1f s", project.id, run.run_id, seconds)
    return project.id


def wait_for(
    runs: RunService,
    run_id: str,
    statuses: frozenset[str] | set[str],
    timeout: float,
    stop: threading.Event,
) -> str:
    """Poll a run until it reaches one of `statuses`, the time runs out, or `stop` is set."""
    deadline = time.monotonic() + timeout
    while True:
        status = runs.get(run_id).status
        if status in statuses or time.monotonic() >= deadline or stop.wait(0.5):
            return status
