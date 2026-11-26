"""Questions over HTTP: guarded, read-only answers from the newest tested model."""

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from joinpilot.api.main import create_app
from joinpilot.config import KPISettings, LLMSettings, Settings
from joinpilot.db.models import LLMCallRow
from joinpilot.db.session import session_scope
from joinpilot.llm.fake import FakeProvider
from joinpilot.llm.observed import ObservedProvider
from joinpilot.services import questions as questions_module

QUESTION = "What is the open amount in each aging bucket?"
GOOD = (
    'SELECT "aging_bucket" AS bucket, ROUND(SUM("DMBTR"), 2) AS amount '
    'FROM model."v_bsid" GROUP BY 1 ORDER BY 1'
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=tmp_path,
        jobs_mode="inline",
        llm=LLMSettings(provider="fake"),
        kpi=KPISettings(reference_date=date(2026, 6, 30)),
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


def model_answers(monkeypatch: pytest.MonkeyPatch, *sql: str) -> FakeProvider:
    """Make the language model answer with these queries, in turn."""
    replies = iter(sql)
    fake = FakeProvider(
        {
            "qa_sql": lambda _: {
                "sql": next(replies),
                "chart": "bar",
                "explanation": "Sums by bucket.",
            }
        }
    )

    def provider(settings: Settings, log: Any = None) -> ObservedProvider:
        return ObservedProvider(fake, settings.llm, log=log)

    monkeypatch.setattr(questions_module, "make_provider", provider)
    return fake


def built_project(client: TestClient) -> tuple[str, str]:
    project_id: str = client.post("/projects", json={"name": "Q"}).json()["id"]
    client.post(f"/projects/{project_id}/tables", json={"sample": "erp_s1_sap"})
    run = client.post(
        f"/projects/{project_id}/runs", json={"requirement": "Open receivables by aging bucket"}
    ).json()
    proposals = client.get(f"/runs/{run['run_id']}/proposals").json()
    decisions = [
        {"edge_id": p["edge_id"], "action": "approve" if p["recommended"] else "reject"}
        for p in proposals
    ]
    client.post(f"/runs/{run['run_id']}/approvals", json={"decisions": decisions})
    return project_id, run["run_id"]


def ask(client: TestClient, project_id: str, question: str = QUESTION) -> Any:
    return client.post(f"/projects/{project_id}/ask", json={"question": question})


def test_a_question_is_answered_with_its_sql_rows_and_evidence(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, run_id = built_project(client)
    fake = model_answers(monkeypatch, GOOD)
    body = ask(client, project_id).json()
    assert not body["blocked"] and body["reason_code"] is None
    assert body["columns"] == ["bucket", "amount"]
    assert [r["bucket"] for r in body["rows"]] == ["1-30", "31-60", "61-90", "90+", "not_due"]
    assert "LIMIT" not in body["sql"], "the row limit is applied when running, not shown"
    evidence = body["evidence"]
    assert evidence["run_id"] == run_id and evidence["views"] == ["v_bsid"]
    assert evidence["attempts"] == 1 and evidence["row_count"] == 5 and not evidence["truncated"]
    prompt = fake.calls[0].user
    assert '"aging_bucket" VARCHAR: aging bucket of the open item' in prompt
    assert "-- Open receivables by aging bucket" in prompt, "dashboard queries are examples"
    with session_scope(settings.db_url) as session:
        calls = session.scalar(
            select(func.count()).select_from(LLMCallRow).where(LLMCallRow.purpose == "qa_sql")
        )
    assert calls == 1


def test_sql_outside_the_model_is_blocked_after_one_fix(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, _ = built_project(client)
    fake = model_answers(monkeypatch, "SELECT * FROM BSID", "SELECT * FROM KNA1")
    body = ask(client, project_id).json()
    assert body["blocked"] and body["rows"] == [] and body["sql"] is None
    assert body["reason_code"] in {"UNSAFE_SQL", "UNKNOWN_IDENTIFIER"}
    assert len(fake.calls) == 2


def test_without_a_language_model_the_answer_says_so(client: TestClient) -> None:
    project_id, _ = built_project(client)
    body = ask(client, project_id).json()
    assert body["blocked"] and body["reason_code"] == "LLM_UNAVAILABLE"
    assert "qa_sql" in body["message"]


def test_questions_need_a_model_and_a_sensible_length(client: TestClient) -> None:
    project_id: str = client.post("/projects", json={"name": "Empty"}).json()["id"]
    assert ask(client, project_id).status_code == 409
    assert ask(client, project_id, "hi").status_code == 422
    built, _ = built_project(client)
    assert ask(client, built, "x" * 600).status_code == 422
    assert ask(client, "3f0b7c1e-6a2d-4c8e-9b1a-2d5e8f7a9c10").status_code == 404
