"""Rate and size limits, before any endpoint runs."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from joinpilot.api import limits as limits_module
from joinpilot.api.limits import Counter, client_address
from joinpilot.api.main import create_app
from joinpilot.config import LimitSettings, LLMSettings, Settings

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
    assert len(counter._windows) == 10, "the table never grows past its cap"
    counter.hit("late", 5, 60, now=120)
    assert len(counter._windows) == 1, "finished windows are pruned"


def test_a_refused_request_uses_no_budget() -> None:
    counter = Counter()
    rules = [("model:everyone", 1, 86_400.0), ("model:a", 5, 60.0)]
    assert counter.hit_all(rules, now=0) is None
    refused = counter.hit_all([("model:everyone", 1, 86_400.0), ("model:b", 5, 60.0)], now=1)
    assert refused is not None and refused[0][0] == "model:everyone"
    assert ("model:b", 60.0) not in counter._windows, "no window is made for a refused client"
    assert counter.hit("a", 1, 60, now=2) is None


def test_the_client_is_the_hop_a_trusted_proxy_added() -> None:
    scope = {"client": ("10.0.0.1", 1), "headers": [(b"x-forwarded-for", b"6.6.6.6, 203.0.113.7")]}
    assert client_address(scope, 0) == "10.0.0.1", "without proxies the peer counts"
    assert client_address(scope, 1) == "203.0.113.7", "the faked leftmost entry is ignored"
    assert client_address({"client": ("10.0.0.1", 1), "headers": []}, 1) == "10.0.0.1"


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


def test_bodies_without_a_length_are_refused_with_413(tmp_path: Path) -> None:
    api = client(tmp_path, max_body_kb=1)
    chunks = iter([b'{"name": "', b"x" * 2000, b'"}'])
    big = api.post("/projects", content=chunks, headers={"content-type": "application/json"})
    assert big.status_code == 413 and big.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    small = iter([b'{"name": ', b'"Chunked"}'])
    made = api.post("/projects", content=small, headers={"content-type": "application/json"})
    assert made.status_code == 201 and made.json()["name"] == "Chunked"


def test_projects_and_uploads_share_an_hourly_storage_budget(tmp_path: Path) -> None:
    api = client(tmp_path, storage_per_hour=2)
    assert api.post("/projects", json={"name": "a"}).status_code == 201
    upload = api.post(f"/projects/{PROJECT}/tables", files={"files": ("a.csv", b"k\n1\n")})
    assert upload.status_code == 404, "the budget counts the call, not its result"
    refused = api.post("/projects", json={"name": "b"})
    assert refused.status_code == 429
    assert "projects and uploads this hour" in refused.json()["error"]["message"]
    assert api.get("/projects").status_code == 200, "reads are not part of it"


def test_ipv6_clients_share_a_budget_per_64_network() -> None:
    def scope(peer: str) -> Any:
        return {"client": (peer, 1), "headers": []}

    one = client_address(scope("2001:db8:1:2:aaaa::1"), 0)
    assert one == client_address(scope("2001:db8:1:2:ffff::9"), 0) == "2001:db8:1:2::/64"
    assert client_address(scope("2001:db8:1:3::1"), 0) != one
    assert client_address(scope("::ffff:203.0.113.7"), 0) == "203.0.113.7"
    assert client_address(scope("203.0.113.7"), 0) == "203.0.113.7"
    assert client_address(scope("testclient"), 0) == "testclient"
