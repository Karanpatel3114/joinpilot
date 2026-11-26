"""The agent graph. Each node is a small function of the state; dependencies come in
through `AgentContext`, so tests swap in fakes.

Flow: profile -> parse_requirement -> rank_joins -> await_approval (a pause until a
person decides) -> generate_views -> check_views -> [repair_views -> check_views, at
most AGENT__MAX_REPAIRS times] -> build_dashboard -> finish. Runs with no candidates or no approved
joins go straight to finish.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Protocol

import duckdb
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from joinpilot.agent.approval import Decision, apply_decisions
from joinpilot.agent.ranking import rank_joins
from joinpilot.agent.repair import STRUCTURAL, repair_spec
from joinpilot.agent.requirement import ParsedRequirement, parse_requirement
from joinpilot.agent.state import RunState
from joinpilot.checks.sit import run_checks
from joinpilot.config import Settings
from joinpilot.joins.models import JoinCandidate
from joinpilot.joins.scoring import score_candidates
from joinpilot.kpi.compute import Metric, compute_metrics
from joinpilot.kpi.metrics import define_metrics
from joinpilot.llm.provider import LLMProvider
from joinpilot.profiling.models import ProjectProfile
from joinpilot.sqlgen.views import (
    create_views,
    plan_views,
    render_view,
    spec_from_dict,
    spec_to_dict,
)

logger = logging.getLogger(__name__)


class Node(Protocol):
    """A graph step: reads the state and returns the keys it changes."""

    def __call__(self, state: RunState) -> dict[str, Any]: ...


@dataclass
class AgentContext:
    """What the graph's steps need from the outside world."""

    load_profile: Callable[[], ProjectProfile]
    llm: LLMProvider
    settings: Settings
    warehouse: Callable[[], AbstractContextManager[duckdb.DuckDBPyConnection]] | None = None


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
        warnings = list(outcome.warnings)
        if not outcome.proposals:
            warnings.append("No join candidates were found, so there is nothing to approve.")
        return {
            "proposals": [p.model_dump(by_alias=True) for p in outcome.proposals],
            "warnings": warnings,
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

    def generate_views(self, state: RunState) -> dict[str, Any]:
        """Write one guarded view per fact table from the approved joins."""
        specs = plan_views(
            state.get("proposals", []),
            self.profile_data(),
            state.get("requirement", ""),
            self.ctx.settings.kpi,
        )
        with self.open_warehouse() as con:
            views = create_views(con, specs)
        failed = [v.name for v in views if v.status == "failed"]
        return {
            "views": [v.model_dump() for v in views],
            "view_specs": [spec_to_dict(s) for s in specs],
            "warnings": [f"The view {name} could not be created." for name in failed],
            "status": "checking",
        }

    def check_views(self, state: RunState) -> dict[str, Any]:
        """Run the SIT checks on every view that was created."""
        created = {v["name"] for v in state.get("views", []) if v["status"] != "failed"}
        specs = [spec_from_dict(s) for s in state.get("view_specs", []) if s["name"] in created]
        with self.open_warehouse() as con:
            results = run_checks(
                con,
                specs,
                self.profile_data(),
                self.ctx.settings.checks,
                self.ctx.settings.kpi.aging_bucket_edges,
            )
        failed = [r for r in results if not r.passed]
        warnings = [f"{len(failed)} of {len(results)} checks failed."] if failed else []
        round_number = len(state.get("check_rounds", [])) + 1
        summary = {
            "round": round_number,
            "passed": len(results) - len(failed),
            "failed": len(failed),
        }
        return {
            "checks": [r.model_dump() for r in results],
            "check_rounds": [summary],
            "warnings": warnings,
            "status": "checking",
        }

    def repair_views(self, state: RunState) -> dict[str, Any]:
        """Fix views whose checks show duplicated or lost rows, then let them be checked again."""
        failing = {
            c["view"]
            for c in state.get("checks", [])
            if not c["passed"] and c["kind"] in STRUCTURAL
        }
        profile = self.profile_data()
        columns = {t.name: t.columns for t in profile.tables}
        specs, changed, notes = [], [], []
        for saved in state.get("view_specs", []):
            spec = spec_from_dict(saved)
            if spec.name in failing:
                fixed, done = repair_spec(spec, profile, self.ctx.settings.joins)
                notes += done
                if fixed.joins != spec.joins:
                    spec = render_view(
                        fixed, columns, state.get("requirement", ""), self.ctx.settings.kpi
                    )
                    changed.append(spec)
            specs.append(spec)
        attempts = state.get("repair_attempts", 0) + 1
        views = {v["name"]: v for v in state.get("views", [])}
        if changed:
            with self.open_warehouse() as con:
                for view in create_views(con, changed, status="repaired"):
                    views[view.name] = view.model_dump()
                    if view.status == "failed":
                        notes.append(f"The repaired view {view.name} could not be created.")
        else:
            notes.append("No automatic repair was possible for the failing checks.")
            attempts = self.ctx.settings.agent.max_repairs
        return {
            "view_specs": [spec_to_dict(s) for s in specs],
            "views": list(views.values()),
            "repair_attempts": attempts,
            "warnings": notes,
            "status": "repairing",
        }

    def after_checks(self, state: RunState) -> str:
        """Repair while structural checks fail and attempts remain; otherwise finish."""
        failing = any(not c["passed"] and c["kind"] in STRUCTURAL for c in state.get("checks", []))
        if failing and state.get("repair_attempts", 0) < self.ctx.settings.agent.max_repairs:
            return "repair_views"
        return "build_dashboard"

    def build_dashboard(self, state: RunState) -> dict[str, Any]:
        """Define the KPI metrics the model supports and compute them on its views.

        A view that still fails a structural check (lost or duplicated rows) would give
        wrong totals, so its metrics are reported as failed instead of computed. A problem
        here never fails a run whose views and checks are done.
        """
        created = {v["name"] for v in state.get("views", []) if v["status"] != "failed"}
        specs = [spec_from_dict(s) for s in state.get("view_specs", []) if s["name"] in created]
        broken: dict[str, set[str]] = {}
        for check in state.get("checks", []):
            if not check["passed"] and check["kind"] in STRUCTURAL:
                broken.setdefault(check["view"], set()).add(check["kind"])
        kpi = self.ctx.settings.kpi
        try:
            metrics = define_metrics(specs, self.profile_data(), state.get("requirement", ""), kpi)
            usable = [m for m in metrics if m.view not in broken]
            with self.open_warehouse() as con:
                computed = {
                    m.metric_id: m for m in compute_metrics(con, usable, kpi.max_metric_rows)
                }
        except Exception as error:  # the model is done; the dashboard is extra
            logger.warning("dashboard failed: %s", type(error).__name__)
            return {"metrics": [], "warnings": ["The KPI dashboard could not be built."]}
        results = [
            computed.get(m.metric_id)
            or Metric(
                **m.model_dump(),
                data=[],
                status="failed",
                message=(
                    f"Not computed: the view {m.view} failed its "
                    f"{', '.join(sorted(broken[m.view]))} checks, so its totals would be wrong."
                ),
            )
            for m in metrics
        ]
        failed = [m.title for m in results if m.status == "failed"]
        return {
            "metrics": [m.model_dump() for m in results],
            "warnings": [f"The metric {title!r} was not computed." for title in failed],
        }

    def finish(self, state: RunState) -> dict[str, Any]:
        """Close the run."""
        return {"status": "completed"}

    def open_warehouse(self) -> AbstractContextManager[duckdb.DuckDBPyConnection]:
        """The project's warehouse; every graph that builds views needs one."""
        if self.ctx.warehouse is None:
            raise RuntimeError("This graph has no warehouse to build views in.")
        return self.ctx.warehouse()


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
    graph.add_node("generate_views", timed("generate_views", nodes.generate_views))
    graph.add_node("check_views", timed("check_views", nodes.check_views))
    graph.add_node("repair_views", timed("repair_views", nodes.repair_views))
    graph.add_node("build_dashboard", timed("build_dashboard", nodes.build_dashboard))
    graph.add_node("finish", timed("finish", nodes.finish))
    graph.add_conditional_edges(
        "rank_joins",
        lambda state: "await_approval" if state.get("proposals") else "finish",
        ["await_approval", "finish"],
    )
    graph.add_conditional_edges(
        "await_approval",
        lambda state: "generate_views" if state.get("status") == "generating" else "finish",
        ["generate_views", "finish"],
    )
    graph.add_edge("generate_views", "check_views")
    graph.add_conditional_edges(
        "check_views", nodes.after_checks, ["repair_views", "build_dashboard"]
    )
    graph.add_edge("build_dashboard", "finish")
    graph.add_edge("repair_views", "check_views")
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=checkpointer)
