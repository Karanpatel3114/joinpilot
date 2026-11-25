from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from joinpilot.agent.graph import AgentContext, build_graph
from joinpilot.agent.ranking import template_explanation
from joinpilot.agent.state import add_unique, merge_dicts
from joinpilot.joins.models import JoinCandidate
from joinpilot.llm.fake import FakeProvider
from joinpilot.llm.provider import Prompt


def test_graph_runs_every_step_and_records_timings(ctx: AgentContext) -> None:
    state = build_graph(ctx).invoke({"run_id": "r1", "requirement": "Open receivables by customer"})
    assert set(state["timings_ms"]) == {"profile", "parse_requirement", "rank_joins"}
    assert len(state["candidates"]) > 5
    assert sum(p["recommended"] for p in state["proposals"]) == 5
    assert state["status"] == "awaiting_approval"


def test_state_is_checkpointed_per_run(ctx: AgentContext) -> None:
    saver = InMemorySaver()
    graph = build_graph(ctx, checkpointer=saver)
    config = {"configurable": {"thread_id": "run-42"}}
    graph.invoke({"run_id": "run-42", "requirement": "Revenue by product group"}, config)
    snapshot = graph.get_state(config)
    assert snapshot.values["run_id"] == "run-42"
    assert snapshot.next == ()


def test_timings_merge_instead_of_overwriting() -> None:
    assert merge_dicts({"a": 1.0}, {"b": 2.0}) == {"a": 1.0, "b": 2.0}


def test_reducers_skip_repeated_warnings() -> None:
    assert add_unique(["a"], ["a", "b"]) == ["a", "b"]


def test_graph_uses_the_model_when_it_answers(ctx: AgentContext, fake_llm: FakeProvider) -> None:
    fake_llm.on("parse_requirement", lambda p: {"summary": "Aging", "relevant_tables": ["BSID"]})

    def rank(prompt: Prompt) -> dict[str, Any]:
        state = graph_state["candidates"]
        joins = [
            {
                "edge_id": c["edge_id"],
                "include": True,
                "relevance": "required",
                "explanation": template_explanation(JoinCandidate.model_validate(c)),
            }
            for c in state
            if c["accepted"]
        ]
        return {"joins": joins}

    graph_state: dict[str, Any] = {}
    fake_llm.on("rank_joins", rank)
    graph = build_graph(ctx)
    for update in graph.stream({"run_id": "r", "requirement": "Aging"}, stream_mode="values"):
        graph_state.update(update)
    assert graph_state["parsed_requirement"]["source"] == "llm"
    recommended = [p for p in graph_state["proposals"] if p["recommended"]]
    assert len(recommended) == 5 and all(p["explanation_source"] == "llm" for p in recommended)
