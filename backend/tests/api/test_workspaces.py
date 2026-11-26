"""Private workspaces: projects and runs are only served to the workspace that owns them."""

import io
import uuid

from fastapi.testclient import TestClient

from joinpilot.config import Settings
from joinpilot.db.models import RunRow
from joinpilot.db.session import session_scope
from joinpilot.services.projects import ProjectService
from joinpilot.workspaces import DEMO

ALICE = {"X-Workspace": "alice-0123456789abcdef"}
BOB = {"X-Workspace": "bob-0123456789abcdef00"}


def settings_of(client: TestClient) -> Settings:
    settings: Settings = client.app.state.settings  # type: ignore[attr-defined]
    return settings


def add_run(settings: Settings, project_id: str) -> str:
    run_id = str(uuid.uuid4())
    with session_scope(settings.db_url) as session:
        session.add(RunRow(id=run_id, project_id=project_id, requirement="x", status="queued"))
    return run_id


def test_each_workspace_sees_only_its_own_projects(client: TestClient) -> None:
    mine = client.post("/projects", json={"name": "Alice's"}, headers=ALICE).json()
    assert mine["read_only"] is False
    assert [p["id"] for p in client.get("/projects", headers=ALICE).json()] == [mine["id"]]
    assert client.get("/projects", headers=BOB).json() == []
    assert client.get("/projects").json() == [], "no header means the local workspace"


def test_another_workspaces_project_and_runs_are_not_found(client: TestClient) -> None:
    project = client.post("/projects", json={"name": "Alice's"}, headers=ALICE).json()["id"]
    run = add_run(settings_of(client), project)
    assert client.get(f"/runs/{run}", headers=ALICE).status_code == 200
    for method, path in [
        ("GET", f"/projects/{project}/profile"),
        ("GET", f"/projects/{project}/runs"),
        ("POST", f"/projects/{project}/runs"),
        ("POST", f"/projects/{project}/ask"),
        ("GET", f"/runs/{run}"),
        ("GET", f"/runs/{run}/checks"),
        ("GET", f"/runs/{run}/export"),
    ]:
        response = client.request(
            method, path, headers=BOB, json={"requirement": "Revenue", "question": "How many?"}
        )
        assert response.status_code == 404, (method, path)
        assert response.json()["error"]["code"] == "NOT_FOUND"
    link = client.get(f"/runs/{run}/export?workspace={ALICE['X-Workspace']}")
    assert link.status_code == 200, "download links carry the workspace in the query"


def test_a_malformed_workspace_id_is_refused(client: TestClient) -> None:
    for bad in ["short", "demo", "has spaces in it, sixteen+", "x" * 65]:
        response = client.get("/projects", headers={"X-Workspace": bad})
        assert response.status_code == 422 and response.json()["error"]["code"] == "INVALID_INPUT"


def test_the_demo_project_is_shared_and_read_only(client: TestClient) -> None:
    demo = ProjectService(settings_of(client)).create("Sample ERP", DEMO)
    listed = client.get("/projects", headers=ALICE).json()
    assert [(p["id"], p["read_only"]) for p in listed] == [(demo.id, True)]
    assert client.get(f"/projects/{demo.id}/runs", headers=BOB).json() == []
    upload = client.post(
        f"/projects/{demo.id}/tables",
        headers=ALICE,
        files={"files": ("orders.csv", io.BytesIO(b"id\n1\n"), "text/csv")},
    )
    assert upload.status_code == 409 and "read-only" in upload.json()["error"]["message"]
    run = client.post(f"/projects/{demo.id}/runs", headers=ALICE, json={"requirement": "Revenue"})
    assert run.status_code == 409
    asked = client.post(f"/projects/{demo.id}/ask", headers=ALICE, json={"question": "How many?"})
    assert "read-only" not in asked.json().get("error", {}).get("message", ""), "asking only reads"
