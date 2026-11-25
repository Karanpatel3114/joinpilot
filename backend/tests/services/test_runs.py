"""Run lifecycle rules: transitions are atomic, jobs are idempotent, failures are visible."""

import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select

from joinpilot.agent.approval import Decision
from joinpilot.config import LLMSettings, Settings
from joinpilot.db.models import LLMCallRow
from joinpilot.db.session import session_scope
from joinpilot.errors import ConflictError, JobQueueUnavailableError
from joinpilot.jobs.queue import InlineJobQueue, JobName
from joinpilot.services.projects import ProjectService
from joinpilot.services.runs import RunService


class RecordingQueue:
    """Remembers jobs instead of running them; can be told to fail."""

    def __init__(self, fail: bool = False) -> None:
        self.jobs: list[tuple[JobName, str]] = []
        self.fail = fail

    def submit(self, name: JobName, run_id: str) -> None:
        if self.fail:
            raise ConnectionError("redis is down")
        self.jobs.append((name, run_id))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path, llm=LLMSettings(provider="fake"))


@pytest.fixture
def project(settings: Settings) -> str:
    projects = ProjectService(settings)
    record = projects.create("Lifecycle")
    projects.add_sample(record.id, "erp_s1_sap")
    return record.id


def paused_run(settings: Settings, project: str) -> tuple[RunService, str]:
    service = RunService(settings, InlineJobQueue(settings))
    run = service.start(project, "Open receivables by customer")
    assert run.status == "awaiting_approval"
    return service, run.run_id


def approve_first(service: RunService, run_id: str) -> None:
    edge = service.proposals(run_id)[0]["edge_id"]
    service.approve(run_id, [Decision(edge_id=edge, action="approve")])


def llm_calls(settings: Settings) -> int:
    with session_scope(settings.db_url) as session:
        return int(session.scalar(select(func.count()).select_from(LLMCallRow)) or 0)


def test_only_one_of_two_concurrent_approvals_wins(settings: Settings, project: str) -> None:
    service, run_id = paused_run(settings, project)
    queued = RunService(settings, RecordingQueue())
    edge = service.proposals(run_id)[0]["edge_id"]

    def approve() -> str:
        try:
            queued.approve(run_id, [Decision(edge_id=edge, action="approve")])
            return "ok"
        except ConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(lambda _: approve(), range(2)))
    assert outcomes == ["conflict", "ok"]


def test_redelivered_jobs_do_not_rerun_a_finished_run(settings: Settings, project: str) -> None:
    service, run_id = paused_run(settings, project)
    approve_first(service, run_id)
    assert service.get(run_id).status == "completed"
    calls = llm_calls(settings)
    service.execute(run_id)
    service.resume(run_id)
    assert service.get(run_id).status == "completed"
    assert llm_calls(settings) == calls


def test_a_duplicate_start_job_leaves_a_paused_run_paused(settings: Settings, project: str) -> None:
    service, run_id = paused_run(settings, project)
    calls = llm_calls(settings)
    service.execute(run_id)
    assert service.get(run_id).status == "awaiting_approval"
    assert llm_calls(settings) == calls


def test_a_failed_enqueue_marks_a_new_run_failed(settings: Settings, project: str) -> None:
    service = RunService(settings, RecordingQueue(fail=True))
    with pytest.raises(JobQueueUnavailableError):
        service.start(project, "Revenue by product group")
    [run] = service.list_for_project(project)
    assert run.status == "failed" and run.error == "The run could not be queued."


def test_a_failed_resume_enqueue_restores_the_pause(settings: Settings, project: str) -> None:
    _, run_id = paused_run(settings, project)
    failing = RunService(settings, RecordingQueue(fail=True))
    with pytest.raises(JobQueueUnavailableError):
        approve_first(failing, run_id)
    assert failing.get(run_id).status == "awaiting_approval"
    assert all(p["status"] == "proposed" for p in failing.proposals(run_id))
    approve_first(RunService(settings, InlineJobQueue(settings)), run_id)


def test_a_run_without_candidates_completes_with_a_warning(settings: Settings) -> None:
    projects = ProjectService(settings)
    record = projects.create("Single table")
    projects.add_upload(record.id, "items.csv", io.BytesIO(b"id,name\n1,a\n2,b\n"))
    service = RunService(settings, InlineJobQueue(settings))
    run = service.start(record.id, "Count items")
    assert run.status == "completed"
    assert any("nothing to approve" in w for w in run.warnings)


def test_recovery_requeues_runs_a_restart_left_active(settings: Settings, project: str) -> None:
    queue = RecordingQueue()
    service = RunService(settings, queue)
    run = service.start(project, "Revenue by product group")
    assert service.get(run.run_id).status == "queued"
    assert service.recover() == 1
    assert queue.jobs[-1] == ("resume_run", run.run_id)
    RunService(settings, InlineJobQueue(settings)).resume(run.run_id)
    assert service.get(run.run_id).status == "awaiting_approval"


def test_unexpected_errors_fail_the_run_without_leaking_details(
    settings: Settings, project: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = RunService(settings, RecordingQueue())
    run = service.start(project, "Revenue by product group")

    def boom(*args: Any) -> None:
        raise RuntimeError("secret /internal/path")

    monkeypatch.setattr(service.projects, "profile", boom)
    service.execute(run.run_id)
    failed = service.get(run.run_id)
    assert failed.status == "failed"
    assert (
        failed.error is not None and "secret" not in failed.error and "RuntimeError" in failed.error
    )


def test_a_timed_out_arq_job_marks_the_run_failed(
    settings: Settings, project: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio

    import joinpilot.jobs.worker as worker

    service = RunService(settings, RecordingQueue())
    run = service.start(project, "Revenue by product group")

    async def cancelled(*args: Any) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(worker.asyncio, "to_thread", cancelled)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(worker.start_run({"settings": settings}, run.run_id))
    assert service.get(run.run_id).status == "failed"
