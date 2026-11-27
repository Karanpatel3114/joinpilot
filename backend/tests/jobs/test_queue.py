import os
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import joinpilot.jobs.queue as queue
from joinpilot.api.main import create_app
from joinpilot.config import LLMSettings, Settings


def test_queues_follow_the_jobs_mode(tmp_path: Path) -> None:
    def make(mode: str, redis: str = "") -> object:
        return queue.make_job_queue(
            Settings(_env_file=None, data_dir=tmp_path, jobs_mode=mode, redis_url=redis)
        )  # type: ignore[arg-type]

    assert isinstance(make("inline"), queue.InlineJobQueue)
    assert isinstance(make("thread"), queue.ThreadJobQueue)
    assert isinstance(make("arq", "redis://localhost:6379/0"), queue.ArqJobQueue)
    with pytest.raises(ValueError, match="REDIS_URL"):
        make("arq")


def test_arq_queue_gives_every_submit_its_own_job_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sent: list[tuple[Any, ...]] = []

    class FakePool:
        async def enqueue_job(self, name: str, run_id: str, _job_id: str) -> None:
            sent.append((name, run_id, _job_id))

        async def aclose(self) -> None:
            sent.append(("closed",))

    async def fake_create_pool(settings: Any) -> FakePool:
        return FakePool()

    monkeypatch.setattr(queue, "create_pool", fake_create_pool)
    settings = Settings(
        _env_file=None, data_dir=tmp_path, jobs_mode="arq", redis_url="redis://x:6379"
    )
    arq = queue.ArqJobQueue(settings)
    arq.submit("resume_run", "r1")
    arq.submit("resume_run", "r1")
    first, second = sent[0], sent[2]
    assert first[:2] == second[:2] == ("resume_run", "r1")
    assert first[2].startswith("resume_run:r1:") and first[2] != second[2]
    assert sent[1] == sent[3] == ("closed",)


def wait_for(client: TestClient, run_id: str, status: str, seconds: float = 60) -> dict[str, Any]:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        run: dict[str, Any] = client.get(f"/runs/{run_id}").json()
        if run["status"] in (status, "failed"):
            return run
        time.sleep(0.2)
    raise AssertionError(f"run {run_id} did not reach {status}")


@pytest.mark.integration
def test_runs_flow_through_redis_and_the_in_process_worker(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        jobs_mode="arq",
        redis_url=os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/0"),
        llm=LLMSettings(provider="fake"),
    )
    with TestClient(create_app(settings)) as client:
        project = client.post("/projects", json={"name": "Queued"}).json()["id"]
        client.post(f"/projects/{project}/tables", json={"sample": "erp_s1_sap"})
        run = client.post(
            f"/projects/{project}/runs", json={"requirement": "Revenue by product group"}
        ).json()
        assert run["status"] == "queued"
        waiting = wait_for(client, run["run_id"], "awaiting_approval")
        assert waiting["status"] == "awaiting_approval", waiting["error"]
        edge = client.get(f"/runs/{run['run_id']}/proposals").json()[0]["edge_id"]
        client.post(
            f"/runs/{run['run_id']}/approvals",
            json={"decisions": [{"edge_id": edge, "action": "approve"}]},
        )
        assert wait_for(client, run["run_id"], "completed")["status"] == "completed"
