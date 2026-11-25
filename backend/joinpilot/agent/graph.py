"""The agent graph. Each node is a small function of the state; dependencies come in
through `AgentContext`, so tests swap in fakes.

Flow so far: profile -> parse_requirement -> rank_joins -> await_approval (a pause
until a person decides). M6 adds view generation, checks and repair after approval.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from joinpilot.agent.approval import Decision, apply_decisions
from joinpilot.agent.ranking import rank_joins
from joinpilot.agent.requirement import ParsedRequirement, parse_requirement
from joinpilot.agent.state import RunState
from joinpilot.config import Settings
from joinpilot.joins.models import JoinCandidate
from joinpilot.joins.scoring import score_candidates
from joinpilot.llm.provider import LLMProvider
from joinpilot.profiling.models import ProjectProfile


class Node(Protocol):
    """A graph step: reads the state and returns the keys it changes."""

    def __call__(self, state: RunState) -> dict[str, Any]: ...


@dataclass
class AgentContext:
    """What the graph's steps need from the outside world."""

    load_profile: Callable[[], ProjectProfile]
    llm: LLMProvider
    settings: Settings


def timed(name: str, node: Node) -> Node:
    """Wrap a node so its duration is recorded in `timings_ms`."""

    def run(state: RunState) -> dict[str, Any]:
        started = time.perf_counter()
        update = node(state)
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        return {**update, "timings_ms": {name: elapsed}}

    return run


def candidates_of(state: RunState) -> list[JoinCandidate]:
    """The scored candidates stored in the state, as models."""
    return [JoinCandidate.model_validate(c) for c in state.get("candidates", [])]


class AgentNodes:
    """The graph's steps, bound to one context."""

    def __init__(self, ctx: AgentContext) -> None:
        self.ctx = ctx
        self._profile: ProjectProfile | None = None

    def profile_data(self) -> ProjectProfile:
        """The project's profile, loaded once per graph."""
        if self._profile is None:
            self._profile = self.ctx.load_profile()
        return self._profile

    def profile(self, state: RunState) -> dict[str, Any]:
        """Score every join candidate from the project's profile (deterministic)."""
        candidates = score_candidates(self.profile_data(), self.ctx.settings.joins)
        return {
            "status": "ranking",
            "candidates": [c.model_dump(by_alias=True) for c in candidates],
        }

    def parse_requirement(self, state: RunState) -> dict[str, Any]:
        """Turn the requirement into entities, measures, dimensions, filters and tables."""
        parsed, warnings = parse_requirement(
            state["requirement"], self.profile_data(), self.ctx.llm, self.ctx.settings.agent
        )
        return {"parsed_requirement": parsed.model_dump(), "warnings": warnings}

    def rank_joins(self, state: RunState) -> dict[str, Any]:
        """Rank and explain the candidates for this requirement."""
        parsed = ParsedRequirement.model_validate(state["parsed_requirement"])
        settings = self.ctx.settings
        outcome = rank_joins(
            parsed, candidates_of(state), self.ctx.llm, settings.agent, settings.joins.unique_min
        )
        return {
            "proposals": [p.model_dump(by_alias=True) for p in outcome.proposals],
            "warnings": outcome.warnings,
            "status": "awaiting_approval",
        }

    def await_approval(self, state: RunState) -> dict[str, Any]:
        """Pause until a person decides; resume with a list of decisions.

        LangGraph runs this step again on resume, and `interrupt` then returns the
        decisions, so everything before it must be free of side effects.
        """
        raw = interrupt(
            {
                "run_id": state.get("run_id"),
                "edge_ids": [p["edge_id"] for p in state.get("proposals", [])],
            }
        )
        decisions = [Decision.model_validate(d) for d in raw]
        proposals, warnings = apply_decisions(state.get("proposals", []), decisions)
        approved = [p for p in proposals if p.get("status") == "approved"]
        if not approved:
            warnings.append("No join was approved, so no views will be built.")
        return {
            "proposals": proposals,
            "decisions": [d.model_dump() for d in decisions],
            "warnings": warnings,
            "status": "generating" if approved else "completed",
        }


def build_graph(
    ctx: AgentContext, checkpointer: BaseCheckpointSaver[Any] | None = None
) -> CompiledStateGraph[RunState, None, RunState, RunState]:
    """Compile the agent graph, optionally with a checkpointer for resumable runs."""
    nodes = AgentNodes(ctx)
    graph = StateGraph(RunState)
    graph.add_node("profile", timed("profile", nodes.profile))
    graph.add_node("parse_requirement", timed("parse_requirement", nodes.parse_requirement))
    graph.add_node("rank_joins", timed("rank_joins", nodes.rank_joins))
    graph.add_node("await_approval", timed("await_approval", nodes.await_approval))
    graph.add_edge(START, "profile")
    graph.add_edge("profile", "parse_requirement")
    graph.add_edge("parse_requirement", "rank_joins")
    graph.add_edge("rank_joins", "await_approval")
    graph.add_edge("await_approval", END)
    return graph.compile(checkpointer=checkpointer)
