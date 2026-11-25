"""The whole approval flow over HTTP, with jobs run inline and no language model."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from joinpilot.api.main import create_app
from joinpilot.config import LLMSettings, Settings
from joinpilot.db.models import LLMCallRow
from joinpilot.db.session import session_scope


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None, data_dir=tmp_path, jobs_mode="inline", llm=LLMSettings(provider="fake")
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


def project_with_sample(client: TestClient) -> str:
    project_id: str = client.post("/projects", json={"name": "Demo"}).json()["id"]
    client.post(f"/projects/{project_id}/tables", json={"sample": "erp_s1_sap"})
    return project_id


def start(client: TestClient, project_id: str) -> dict[str, Any]:
    response = client.post(
        f"/projects/{project_id}/runs",
        json={"requirement": "Open receivables by customer and aging bucket"},
    )
    assert response.status_code == 202
    body: dict[str, Any] = response.json()
    return body


def test_a_run_pauses_for_approval_then_completes(client: TestClient, settings: Settings) -> None:
    project_id = project_with_sample(client)
    run = start(client, project_id)
    assert run["status"] == "awaiting_approval"
    assert run["parsed_requirement"]["source"] == "fallback"
    assert {"profile", "parse_requirement", "rank_joins"} <= set(run["timings_ms"])

    proposals = client.get(f"/runs/{run['run_id']}/proposals").json()
    recommended = [p for p in proposals if p["recommended"]]
    assert len(recommended) == 5
    assert all(p["status"] == "proposed" and p["explanation"] for p in proposals)
    bsid = next(p for p in proposals if p["from"] == "BSID.KUNNR")
    assert bsid["normalization"] == "lpad_zeros:10"

    decisions = [{"edge_id": p["edge_id"], "action": "approve"} for p in recommended[:4]]
    decisions.append({"edge_id": recommended[4]["edge_id"], "action": "reject", "reason": "later"})
    response = client.post(f"/runs/{run['run_id']}/approvals", json={"decisions": decisions})
    assert response.status_code == 202

    finished = client.get(f"/runs/{run['run_id']}").json()
    assert finished["status"] == "completed"
    after = {p["edge_id"]: p for p in client.get(f"/runs/{run['run_id']}/proposals").json()}
    assert after[recommended[4]["edge_id"]]["status"] == "rejected"
    assert after[recommended[4]["edge_id"]]["decision_reason"] == "later"
    assert after[recommended[0]["edge_id"]]["status"] == "approved"
    assert [r["run_id"] for r in client.get(f"/projects/{project_id}/runs").json()] == [
        run["run_id"]
    ]
    with session_scope(settings.db_url) as session:
        assert session.scalar(select(func.count()).select_from(LLMCallRow)) >= 2


def test_approval_rules_are_enforced(client: TestClient) -> None:
    project_id = project_with_sample(client)
    run = start(client, project_id)
    url = f"/runs/{run['run_id']}/approvals"
    unknown = client.post(url, json={"decisions": [{"edge_id": "e999", "action": "approve"}]})
    assert unknown.status_code == 422 and unknown.json()["error"]["details"]["edge_ids"] == ["e999"]
    assert client.post(url, json={"decisions": []}).status_code == 422
    edge = client.get(f"/runs/{run['run_id']}/proposals").json()[0]["edge_id"]
    assert (
        client.post(url, json={"decisions": [{"edge_id": edge, "action": "approve"}]}).status_code
        == 202
    )
    again = client.post(url, json={"decisions": [{"edge_id": edge, "action": "approve"}]})
    assert again.status_code == 409 and again.json()["error"]["code"] == "CONFLICT"


def test_runs_need_tables_a_requirement_and_a_real_id(client: TestClient) -> None:
    empty = client.post("/projects", json={"name": "Empty"}).json()["id"]
    assert (
        client.post(f"/projects/{empty}/runs", json={"requirement": "Revenue"}).status_code == 409
    )
    assert client.post(f"/projects/{empty}/runs", json={"requirement": "x"}).status_code == 422
    assert client.get("/runs/8a5b2c3e-0000-4000-8000-000000000000").status_code == 404
    assert client.get("/runs/not-a-uuid").status_code == 422
