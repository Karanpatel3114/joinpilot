from langgraph.checkpoint.memory import InMemorySaver

from joinpilot.agent.graph import AgentContext, build_graph
from joinpilot.agent.state import merge_dicts


def test_graph_runs_every_step_and_records_timings(ctx: AgentContext) -> None:
    state = build_graph(ctx).invoke({"run_id": "r1", "requirement": "Open receivables by customer"})
    assert set(state["timings_ms"]) == {"profile", "parse_requirement", "rank_joins"}
    assert len(state["candidates"]) > 5
    assert len(state["proposals"]) == 5
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
