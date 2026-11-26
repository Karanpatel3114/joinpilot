"""Run state carried between graph steps and saved by the checkpointer.

Values are plain JSON-compatible data so a checkpoint can be stored in Postgres
and a run can resume in another process.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

RunStatus = Literal[
    "queued",
    "profiling",
    "ranking",
    "awaiting_approval",
    "generating",
    "checking",
    "repairing",
    "completed",
    "failed",
]


def add_unique(left: list[str], right: list[str]) -> list[str]:
    """Reducer: append new warnings, skipping ones already recorded (steps may rerun)."""
    return left + [w for w in right if w not in left]


def merge_dicts(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    """Reducer: later steps add their timings without dropping earlier ones."""
    return {**left, **right}


class RunState(TypedDict, total=False):
    """Everything one run knows. Each step returns only the keys it changes."""

    run_id: str
    project_id: str
    requirement: str
    status: RunStatus
    candidates: list[dict[str, Any]]
    parsed_requirement: dict[str, Any] | None
    proposals: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    views: list[dict[str, Any]]
    view_specs: list[dict[str, Any]]
    checks: list[dict[str, Any]]
    repair_attempts: int
    error: str | None
    timings_ms: Annotated[dict[str, float], merge_dicts]
    warnings: Annotated[list[str], add_unique]
