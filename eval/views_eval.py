"""View validity and SIT pass rates, measured by driving the real agent graph offline.

Two reviewer modes (docs/eval-plan.md):
- approve_all: every proposed join is approved, with no human judgement at all;
- oracle: only the true joins are approved (the harness reads gold; the app never does).
"""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from eval.datasets import EvalDataset
from eval.gold import GOLD_ROOT, load_joins
from eval.llm_systems import requirement_for
from joinpilot.agent.graph import AgentContext, build_graph
from joinpilot.config import Settings
from joinpilot.llm.factory import UnavailableProvider

MODES = ("approve_all", "oracle")


def decide(
    mode: str, proposals: list[dict[str, Any]], truth: set[tuple[str, str]]
) -> list[dict[str, Any]]:
    """The reviewer's decisions for one mode."""

    def approved(p: dict[str, Any]) -> bool:
        return mode == "approve_all" or (p["from"], p["to"]) in truth

    return [
        {"edge_id": p["edge_id"], "action": "approve" if approved(p) else "reject"}
        for p in proposals
    ]


def run_mode(
    dataset: EvalDataset, mode: str, settings: Settings, gold_root: Path
) -> dict[str, Any]:
    """Run the graph from requirement to finished views for one dataset and reviewer."""
    ctx = AgentContext(
        load_profile=lambda: dataset.profile,
        llm=UnavailableProvider("evaluation runs the deterministic path"),
        settings=settings,
        warehouse=lambda: nullcontext(dataset.con),
    )
    graph = build_graph(ctx, checkpointer=InMemorySaver())
    config: Any = {"configurable": {"thread_id": f"{dataset.dataset_id}:{mode}"}}
    paused = graph.invoke(
        {"run_id": mode, "requirement": requirement_for(dataset.dataset_id)}, config
    )
    truth = {(e.from_, e.to) for e in load_joins(dataset.dataset_id, gold_root).edges}
    final = graph.invoke(Command(resume=decide(mode, paused.get("proposals", []), truth)), config)
    views = final.get("views", [])
    rounds = final.get("check_rounds", [])
    first = rounds[0] if rounds else {"passed": 0, "failed": 0}
    last = rounds[-1] if rounds else first
    return {
        "views": len(views),
        "views_valid": sum(v["status"] != "failed" for v in views),
        "views_repaired": sum(v["status"] == "repaired" for v in views),
        "checks_first": first["passed"] + first["failed"],
        "checks_passed_first": first["passed"],
        "checks_final": last["passed"] + last["failed"],
        "checks_passed_final": last["passed"],
        "repair_attempts": int(final.get("repair_attempts", 0)),
        "approved": sum(p.get("status") == "approved" for p in final.get("proposals", [])),
    }


def rate(part: int, whole: int) -> float | None:
    """A share, or None when undefined."""
    return round(part / whole, 4) if whole else None


def evaluate_views(
    datasets: list[EvalDataset], settings: Settings, gold_root: Path = GOLD_ROOT
) -> dict[str, Any]:
    """Per mode: view validity, first-try and final check pass rates, repairs."""
    results: dict[str, Any] = {}
    for mode in MODES:
        per_dataset = {d.dataset_id: run_mode(d, mode, settings, gold_root) for d in datasets}
        total = {
            k: sum(r[k] for r in per_dataset.values()) for k in next(iter(per_dataset.values()))
        }
        results[mode] = {
            "aggregate": {
                "view_validity": rate(total["views_valid"], total["views"]),
                "check_pass_first": rate(total["checks_passed_first"], total["checks_first"]),
                "check_pass_final": rate(total["checks_passed_final"], total["checks_final"]),
                "avg_repair_attempts": round(total["repair_attempts"] / len(per_dataset), 3),
                **total,
            },
            "per_dataset": per_dataset,
        }
    return results
