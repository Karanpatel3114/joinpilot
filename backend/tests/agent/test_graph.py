import os
from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from joinpilot.agent.checkpoints import open_checkpointer, psycopg_url
from joinpilot.agent.graph import AgentContext, build_graph
from joinpilot.agent.ranking import template_explanation
from joinpilot.agent.state import add_unique, merge_dicts
from joinpilot.config import Settings
from joinpilot.joins.models import JoinCandidate
from joinpilot.llm.fake import FakeProvider
from joinpilot.llm.provider import Prompt

START = {"run_id": "r1", "requirement": "Open receivables by customer"}


def config(thread: str) -> Any:
    return {"configurable": {"thread_id": thread}}


def test_graph_pauses_for_approval_after_ranking(ctx: AgentContext) -> None:
    graph = build_graph(ctx, checkpointer=InMemorySaver())
    state = graph.invoke(START, config("t1"))
    assert set(state["timings_ms"]) == {"profile", "parse_requirement", "rank_joins"}
    assert sum(p["recommended"] for p in state["proposals"]) == 5
    assert state["status"] == "ranking"
    [pending] = state["__interrupt__"]
    assert len(pending.value["edge_ids"]) == len(state["proposals"])
    assert graph.get_state(config("t1")).next == ("await_approval",)


def resume_with(graph: Any, thread: str, decisions: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = graph.invoke(Command(resume=decisions), config(thread))
    return result


def test_a_new_process_resumes_from_the_saved_checkpoint(ctx: AgentContext, tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path)
    with open_checkpointer(settings) as saver:
        state = build_graph(ctx, saver).invoke(START, config("run-a"))
        recommended = [p["edge_id"] for p in state["proposals"] if p["recommended"]]
    with open_checkpointer(settings) as saver:
        decisions = [{"edge_id": e, "action": "approve"} for e in recommended[:3]]
        decisions.append({"edge_id": recommended[3], "action": "reject", "reason": "not needed"})
        final = resume_with(build_graph(ctx, saver), "run-a", decisions)
    statuses = {p["edge_id"]: p["status"] for p in final["proposals"]}
    assert [statuses[e] for e in recommended] == ["approved"] * 3 + ["rejected", "proposed"]
    assert final["status"] == "completed"
    assert "await_approval" in final["timings_ms"]
    assert {v["status"] for v in final["views"]} == {"created"}
    assert final["checks"] and {"generate_views", "check_views"} <= set(final["timings_ms"])
    assert final["decisions"][3]["reason"] == "not needed"


def test_rejecting_everything_completes_without_views(ctx: AgentContext) -> None:
    graph = build_graph(ctx, checkpointer=InMemorySaver())
    state = graph.invoke(START, config("t2"))
    decisions = [{"edge_id": p["edge_id"], "action": "reject"} for p in state["proposals"]]
    decisions.append({"edge_id": "e999", "action": "approve"})
    final = resume_with(graph, "t2", decisions)
    assert final["status"] == "completed"
    assert any("unknown join e999" in w for w in final["warnings"])
    assert any("No join was approved" in w for w in final["warnings"])


def test_reducers_merge_timings_and_skip_repeated_warnings() -> None:
    assert merge_dicts({"a": 1.0}, {"b": 2.0}) == {"a": 1.0, "b": 2.0}
    assert add_unique(["a"], ["a", "b"]) == ["a", "b"]


def test_graph_uses_the_model_when_it_answers(ctx: AgentContext, fake_llm: FakeProvider) -> None:
    fake_llm.on("parse_requirement", lambda p: {"summary": "Aging", "relevant_tables": ["BSID"]})
    seen: dict[str, Any] = {}

    def rank(prompt: Prompt) -> dict[str, Any]:
        joins = [
            {
                "edge_id": c["edge_id"],
                "include": True,
                "relevance": "required",
                "explanation": template_explanation(JoinCandidate.model_validate(c)),
            }
            for c in seen["candidates"]
            if c["accepted"]
        ]
        return {"joins": joins}

    fake_llm.on("rank_joins", rank)
    graph = build_graph(ctx, checkpointer=InMemorySaver())
    for update in graph.stream(START, config("t3"), stream_mode="values"):
        seen.update(update)
    assert seen["parsed_requirement"]["source"] == "llm"
    recommended = [p for p in seen["proposals"] if p["recommended"]]
    assert len(recommended) == 5 and all(p["explanation_source"] == "llm" for p in recommended)


def test_postgres_urls_are_converted_for_psycopg() -> None:
    assert psycopg_url("postgresql+psycopg://u:p@h:5432/d") == "postgresql://u:p@h:5432/d"


@pytest.mark.integration
def test_runs_pause_and_resume_on_postgres(ctx: AgentContext, tmp_path: Path) -> None:
    url = os.environ.get(
        "TEST_DATABASE_URL", "postgresql+psycopg://joinpilot:joinpilot@localhost:5432/joinpilot"
    )
    settings = Settings(_env_file=None, data_dir=tmp_path, database_url=url)
    thread = f"pg-{tmp_path.name}"
    with open_checkpointer(settings) as saver:
        state = build_graph(ctx, saver).invoke(START, config(thread))
    first = state["proposals"][0]["edge_id"]
    with open_checkpointer(settings) as saver:
        final = resume_with(
            build_graph(ctx, saver), thread, [{"edge_id": first, "action": "approve"}]
        )
    assert final["status"] == "completed"
