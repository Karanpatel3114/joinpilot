"""Rate and size limits, before any endpoint runs."""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from joinpilot.api import limits as limits_module
from joinpilot.api.limits import Counter, capped
from joinpilot.api.main import create_app
from joinpilot.config import LimitSettings, LLMSettings, Settings
from joinpilot.errors import PayloadTooLargeError

PROJECT = "3f0b7c1e-6a2d-4c8e-9b1a-2d5e8f7a9c10"


def client(tmp_path: Path, **limits: int) -> TestClient:
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        jobs_mode="inline",
        llm=LLMSettings(provider="fake"),
        limits=LimitSettings(**limits),
        cors_origins=["http://console.test"],
    )
    return TestClient(create_app(settings))


def test_each_client_has_a_request_budget(tmp_path: Path) -> None:
    api = client(tmp_path, requests_per_minute=3)
    assert [api.get("/projects").status_code for _ in range(3)] == [200, 200, 200]
    refused = api.get("/projects", headers={"Origin": "http://console.test"})
    assert refused.status_code == 429 and int(refused.headers["retry-after"]) > 0
    assert refused.json()["error"]["code"] == "RATE_LIMITED"
    assert refused.headers["access-control-allow-origin"] == "http://console.test"
    assert api.get("/health").status_code == 200, "health checks are never limited"


def test_runs_and_questions_have_their_own_tighter_budget(tmp_path: Path) -> None:
    api = client(tmp_path, expensive_per_minute=2)
    ask = f"/projects/{PROJECT}/ask"
    first = [api.post(ask, json={"question": "How many customers?"}).status_code for _ in range(2)]
    assert first == [404, 404], "the budget counts the request even when it fails"
    third = api.post(f"/projects/{PROJECT}/runs", json={"requirement": "Revenue by month"})
    assert third.status_code == 429 and "runs and questions" in third.json()["error"]["message"]
    assert api.get("/projects").status_code == 200, "cheap requests still work"


def test_the_global_model_budget_and_pruning() -> None:
    counter = Counter()
    assert counter.hit("model:everyone", 2, 86_400, now=0) is None
    assert counter.hit("model:everyone", 2, 86_400, now=1) is None
    assert counter.hit("model:everyone", 2, 86_400, now=2) == pytest.approx(86_398)
    assert counter.hit("model:everyone", 2, 86_400, now=86_401) is None, "a new day starts over"


def test_pruning_forgets_finished_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(limits_module, "MAX_WINDOWS", 10)
    counter = Counter()
    for i in range(20):
        counter.hit(f"client-{i}", 5, 60, now=0)
    counter.hit("late", 5, 60, now=120)
    assert len(counter._windows) <= 11


def test_large_bodies_are_refused_but_uploads_keep_their_own_limit(tmp_path: Path) -> None:
    api = client(tmp_path, max_body_kb=1)
    big = api.post("/projects", json={"name": "x" * 2000})
    assert big.status_code == 413 and big.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    project = api.post("/projects", json={"name": "Uploads"}).json()["id"]
    upload = api.post(
        f"/projects/{project}/tables",
        files={"files": ("orders.csv", "order_id,amount\n" + "A1,10.00\n" * 500, "text/csv")},
    )
    assert upload.status_code == 201


def test_bodies_without_a_length_are_counted() -> None:
    chunks = iter([{"type": "http.request", "body": b"x" * 600, "more_body": True}] * 3)

    async def receive() -> dict[str, object]:
        return next(chunks)

    async def read_all() -> None:
        reader = capped(receive, 1024)  # type: ignore[arg-type]
        for _ in range(3):
            await reader()

    with pytest.raises(PayloadTooLargeError):
        asyncio.run(read_all())
