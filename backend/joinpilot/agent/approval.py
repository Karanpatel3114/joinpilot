"""A person's decisions on proposed joins. Nothing is built until at least one is approved."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Decision(BaseModel):
    """Approve or reject one proposed join, with an optional reason."""

    edge_id: str
    action: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=500)


def apply_decisions(
    proposals: list[dict[str, Any]], decisions: list[Decision]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Mark proposals approved or rejected; unknown edge ids are reported, not applied."""
    by_edge = {d.edge_id: d for d in decisions}
    updated = []
    for proposal in proposals:
        decision = by_edge.get(proposal["edge_id"])
        if decision is None:
            updated.append(proposal)
            continue
        status = "approved" if decision.action == "approve" else "rejected"
        updated.append({**proposal, "status": status, "decision_reason": decision.reason})
    known = {p["edge_id"] for p in proposals}
    warnings = [
        f"A decision named an unknown join {e}; it was ignored." for e in by_edge if e not in known
    ]
    return updated, warnings
