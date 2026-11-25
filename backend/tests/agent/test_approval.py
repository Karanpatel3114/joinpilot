import pytest
from pydantic import ValidationError

from joinpilot.agent.approval import Decision, apply_decisions

PROPOSALS = [{"edge_id": "e1", "status": "proposed"}, {"edge_id": "e2", "status": "proposed"}]


def test_decisions_mark_proposals_and_leave_the_rest_proposed() -> None:
    updated, warnings = apply_decisions(PROPOSALS, [Decision(edge_id="e1", action="approve")])
    assert [p["status"] for p in updated] == ["approved", "proposed"]
    assert warnings == []


def test_unknown_edges_are_reported_and_actions_are_validated() -> None:
    _, warnings = apply_decisions(PROPOSALS, [Decision(edge_id="e9", action="reject")])
    assert warnings == ["A decision named an unknown join e9; it was ignored."]
    with pytest.raises(ValidationError):
        Decision(edge_id="e1", action="maybe")  # type: ignore[arg-type]
