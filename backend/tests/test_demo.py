"""Demo mode builds a finished, read-only sample project once."""

import time
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from joinpilot.api.main import create_app
from joinpilot.config import KPISettings, LLMSettings, Settings
from joinpilot.demo import DEMO_NAME, ensure_demo_project
from joinpilot.jobs.queue import make_job_queue
from joinpilot.services.runs import RunService


def demo_settings(tmp_path: Path, demo_mode: bool = False) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=tmp_path,
        jobs_mode="inline",
        llm=LLMSettings(provider="fake"),
        kpi=KPISettings(reference_date=date(2026, 6, 30)),
        demo_mode=demo_mode,
    )


def test_the_demo_project_is_built_with_a_finished_run_once(tmp_path: Path) -> None:
    settings = demo_settings(tmp_path)
    jobs = make_job_queue(settings)
    project_id = ensure_demo_project(settings, jobs)
    [run] = RunService(settings, jobs).list_for_project(project_id)
    assert run.status == "completed"
    run_id, metrics = RunService(settings, jobs).dashboard(project_id)
    assert run_id == run.run_id and metrics, "the dashboard is ready for visitors"
    assert ensure_demo_project(settings, jobs) == project_id, "a second start keeps it"


def test_demo_mode_builds_it_at_startup_for_every_workspace(tmp_path: Path) -> None:
    with TestClient(create_app(demo_settings(tmp_path, demo_mode=True))) as api:
        deadline = time.monotonic() + 30
        while not (listed := api.get("/projects").json()) and time.monotonic() < deadline:
            time.sleep(0.2)
        assert [(p["name"], p["read_only"]) for p in listed] == [(DEMO_NAME, True)]
        visitor = {"X-Workspace": "visitor-0123456789ab"}
        assert api.get("/projects", headers=visitor).json()[0]["name"] == DEMO_NAME
