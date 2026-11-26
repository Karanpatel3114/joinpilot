"""The MCP tools through a real MCP client session (in-process, and once over stdio)."""

import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from joinpilot.config import KPISettings, LLMSettings, Settings
from joinpilot.llm.fake import FakeProvider
from joinpilot.llm.observed import ObservedProvider
from joinpilot.mcp_server.server import build_server
from joinpilot.services import questions as questions_module

TOOLS = {
    "list_projects",
    "create_project",
    "load_sample",
    "profile_tables",
    "propose_joins",
    "approve_joins",
    "get_run",
    "get_check_results",
    "get_dashboard",
    "ask_question",
    "export_sql",
}
REQUIREMENT = "Open receivables by customer and aging bucket"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=tmp_path,
        llm=LLMSettings(provider="fake"),
        kpi=KPISettings(reference_date=date(2026, 6, 30)),
    )


def session(settings: Settings, steps: Callable[[Client], Awaitable[None]]) -> None:
    async def run() -> None:
        async with Client(build_server(settings)) as client:
            await steps(client)

    asyncio.run(run())


async def call(client: Client, tool: str, **arguments: Any) -> Any:
    result = await client.call_tool(tool, arguments)
    assert not result.is_error, result.content
    return result.structured_content


async def sample_project(client: Client) -> str:
    project = await call(client, "create_project", name="MCP")
    await call(client, "load_sample", project_id=project["project_id"])
    return str(project["project_id"])


def test_every_tool_is_listed_with_a_description_and_schemas(settings: Settings) -> None:
    async def steps(client: Client) -> None:
        tools = {t.name: t for t in (await client.list_tools()).tools}
        assert set(tools) == TOOLS
        for tool in tools.values():
            assert tool.description and tool.input_schema["type"] == "object"
        assert set(tools["approve_joins"].input_schema["required"]) == {"run_id"}
        assert "agreed" in (tools["approve_joins"].description or "")
        assert tools["ask_question"].output_schema is not None

    session(settings, steps)


def test_from_requirement_to_checked_model_and_dashboard(settings: Settings) -> None:
    async def steps(client: Client) -> None:
        project_id = await sample_project(client)
        listed = await call(client, "list_projects")
        assert listed["result"][0]["tables"] == ["BSID", "KNA1", "MAKT", "MARA", "VBAK", "VBAP"]
        profile = await call(client, "profile_tables", project_id=project_id)
        kna1 = next(t for t in profile["tables"] if t["name"] == "KNA1")
        assert kna1["candidate_keys"] == [["KUNNR"]] and profile["overlaps"] > 0
        run = await call(client, "propose_joins", project_id=project_id, requirement=REQUIREMENT)
        assert run["status"] == "awaiting_approval" and run["views"] == []
        recommended = [p for p in run["proposals"] if p["recommended"]]
        assert len(recommended) == 5 and all(p["explanation"] for p in recommended)
        built = await call(client, "approve_joins", run_id=run["run_id"])
        assert built["status"] == "completed"
        assert built["checks_passed"] == built["checks_total"] > 0
        assert {v["name"] for v in built["views"]} == {"v_bsid", "v_vbap"}
        checks = await call(client, "get_check_results", run_id=run["run_id"])
        assert len(checks["result"]) == built["checks_total"]
        dashboard = await call(client, "get_dashboard", project_id=project_id)
        assert dashboard["run_id"] == run["run_id"]
        assert dashboard["metrics"][0]["metric_id"] == "aging_buckets"
        script = await client.call_tool(
            "export_sql", {"run_id": run["run_id"], "dialect": "postgres"}
        )
        assert "CREATE OR REPLACE VIEW" in script.structured_content["result"]

    session(settings, steps)


def test_only_the_chosen_joins_are_approved(settings: Settings) -> None:
    async def steps(client: Client) -> None:
        project_id = await sample_project(client)
        run = await call(client, "propose_joins", project_id=project_id, requirement=REQUIREMENT)
        bsid = next(p["edge_id"] for p in run["proposals"] if p["from"] == "BSID.KUNNR")
        built = await call(
            client, "approve_joins", run_id=run["run_id"], approve=[bsid], reject_reason="later"
        )
        statuses = {p["edge_id"]: p["status"] for p in built["proposals"]}
        assert [e for e, s in statuses.items() if s == "approved"] == [bsid]
        assert [v["name"] for v in built["views"]] == ["v_bsid"]

    session(settings, steps)


def test_errors_come_back_as_plain_tool_errors(settings: Settings) -> None:
    async def steps(client: Client) -> None:
        missing = await client.call_tool("profile_tables", {"project_id": "nope"})
        assert missing.is_error and "NOT_FOUND: Project not found." in missing.content[0].text  # type: ignore[union-attr]
        project_id = await sample_project(client)
        run = await call(client, "propose_joins", project_id=project_id, requirement=REQUIREMENT)
        await call(client, "approve_joins", run_id=run["run_id"])
        again = await client.call_tool("approve_joins", {"run_id": run["run_id"]})
        assert again.is_error and "CONFLICT" in again.content[0].text  # type: ignore[union-attr]

    session(settings, steps)


def test_questions_are_answered_through_the_guarded_path(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    sql = 'SELECT COUNT(*) AS customers FROM "KNA1"'
    fake = FakeProvider({"qa_sql": lambda _: {"sql": sql, "chart": "number", "explanation": "x"}})
    monkeypatch.setattr(
        questions_module,
        "make_provider",
        lambda settings, log=None: ObservedProvider(fake, settings.llm, log=log),
    )

    async def steps(client: Client) -> None:
        project_id = await sample_project(client)
        run = await call(client, "propose_joins", project_id=project_id, requirement=REQUIREMENT)
        await call(client, "approve_joins", run_id=run["run_id"])
        answer = await call(
            client, "ask_question", project_id=project_id, question="How many customers?"
        )
        assert answer["rows"] == [{"customers": 1000}] and not answer["blocked"]
        assert answer["evidence"]["views"] == ["KNA1"]

    session(settings, steps)


def test_the_server_speaks_mcp_over_stdio(tmp_path: Path) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "joinpilot.mcp_server"],
        env={**os.environ, "DATA_DIR": str(tmp_path), "LLM__PROVIDER": "fake"},
        cwd=str(Path(__file__).resolve().parents[3]),
    )

    async def run() -> None:
        async with Client(params) as client:
            assert {t.name for t in (await client.list_tools()).tools} == TOOLS
            result = await client.call_tool("list_projects", {})
            assert not result.is_error and result.structured_content == {"result": []}

    asyncio.run(run())
