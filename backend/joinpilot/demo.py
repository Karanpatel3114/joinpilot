"""Demo mode: a ready, read-only sample project for visitors of the public demo.

With `DEMO_MODE=true` the API builds it in the background at startup: it loads the
synthetic ERP sample into the shared `demo` workspace, runs the agent on an example
requirement, approves the joins the scorer recommends, and lets the run build its
views, checks and dashboard. Free hosts wipe their disk on restart, so this runs on
every start; a project that already exists is kept (D-037).
"""

from __future__ import annotations

import logging
import time

from joinpilot.agent.approval import Decision
from joinpilot.config import Settings
from joinpilot.jobs.queue import JobQueue
from joinpilot.services.projects import ProjectService
from joinpilot.services.runs import RunService
from joinpilot.workspaces import DEMO

logger = logging.getLogger(__name__)

DEMO_NAME = "Sample ERP (read-only)"
DEMO_SAMPLE = "erp_s1_sap"
DEMO_REQUIREMENT = (
    "Open receivables by customer and aging bucket, plus 2026 revenue by product group."
)
SETTLED = frozenset({"awaiting_approval", "completed", "failed"})


def ensure_demo_project(settings: Settings, jobs: JobQueue) -> str:
    """The demo project's id, building it first when the demo workspace is empty."""
    projects = ProjectService(settings)
    existing = projects.list_projects(DEMO)
    if existing:
        return existing[0].id
    started = time.monotonic()
    project = projects.create(DEMO_NAME, DEMO)
    projects.add_sample(project.id, DEMO_SAMPLE)
    runs = RunService(settings, jobs)
    run = runs.start(project.id, DEMO_REQUIREMENT)
    status = wait_for(runs, run.run_id, SETTLED, settings.jobs_timeout_seconds)
    if status == "awaiting_approval":
        decisions = [
            Decision(edge_id=p["edge_id"], action="approve" if p["recommended"] else "reject")
            for p in runs.proposals(run.run_id)
        ]
        runs.approve(run.run_id, decisions)
        status = wait_for(runs, run.run_id, {"completed", "failed"}, settings.jobs_timeout_seconds)
    logger.info(
        "demo project %s built: run %s %s in %.1f s",
        project.id,
        run.run_id,
        status,
        time.monotonic() - started,
    )
    return project.id


def wait_for(
    runs: RunService, run_id: str, statuses: frozenset[str] | set[str], timeout: float
) -> str:
    """Poll a run until it reaches one of `statuses` (or the time runs out)."""
    deadline = time.monotonic() + timeout
    while True:
        status = runs.get(run_id).status
        if status in statuses or time.monotonic() >= deadline:
            return status
        time.sleep(0.5)
