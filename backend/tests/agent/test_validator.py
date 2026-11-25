from typing import Any

import pytest

from joinpilot.agent.ranking import rank_joins, template_explanation
from joinpilot.agent.requirement import ParsedRequirement
from joinpilot.agent.validator import check_explanation
from joinpilot.config import AgentSettings, JoinSettings
from joinpilot.joins.models import JoinCandidate
from joinpilot.joins.scoring import score_candidates
from joinpilot.llm.fake import FakeProvider
from joinpilot.llm.provider import Prompt
from joinpilot.profiling.models import ProjectProfile

SETTINGS = AgentSettings()


@pytest.fixture
def candidates(sap_profile: ProjectProfile) -> list[JoinCandidate]:
    return score_candidates(sap_profile, JoinSettings())


@pytest.fixture
def bsid(candidates: list[JoinCandidate]) -> JoinCandidate:
    return next(c for c in candidates if (c.from_, c.to) == ("BSID.KUNNR", "KNA1.KUNNR"))


def check(candidate: JoinCandidate, text: str, ids: list[str] | None = None) -> list[str]:
    return check_explanation(candidate, text, ids or [], 0.999, 0.6)


def test_a_grounded_explanation_passes(bsid: JoinCandidate) -> None:
    ov = bsid.evidence_roles["inclusion"]
    text = f"{bsid.inclusion_ratio * 100:.0f}% of customer numbers match after padding ({ov})."
    assert check(bsid, text, [ov]) == []


def test_foreign_or_missing_evidence_ids_are_rejected(bsid: JoinCandidate) -> None:
    assert "cites ov_999" in check(bsid, "It matches (ov_999).")[0]
    assert "cites ov_999" in check(bsid, "It matches (OV_999).")[0]
    assert check(bsid, "It obviously matches.") == [
        "cites none of its evidence ids in the explanation text"
    ]
    ov = bsid.evidence_roles["inclusion"]
    assert check(bsid, "   ", [ov]) == ["the explanation is empty"]
    assert "cites none" in check(bsid, "Matches.", [ov])[0]


def test_numbers_must_come_from_the_evidence(bsid: JoinCandidate) -> None:
    ov = bsid.evidence_roles["inclusion"]
    assert check(bsid, f"Exactly 42.0% of values match ({ov}).") == [
        "states 42.0%, which matches no overlap number"
    ]
    assert "matches no" in check(bsid, f"About 42 percent match ({ov}).")[0]
    assert "matches no" in check(bsid, f"A ratio of 0.42 matches ({ov}).")[0]
    assert "in words" in check(bsid, f"Forty-two percent match ({ov}).")[0]


def test_numbers_are_checked_against_the_attribute_they_describe(
    candidates: list[JoinCandidate],
) -> None:
    currency = next(c for c in candidates if (c.from_, c.to) == ("VBAK.WAERK", "BSID.WAERS"))
    ov = currency.evidence_roles["inclusion"]
    assert currency.inclusion_ratio == 1.0
    assert "no uniqueness number" in check(currency, f"BSID.WAERS is 100.0% unique ({ov}).")[0]
    assert check(currency, f"100.0% of VBAK.WAERK values appear in BSID.WAERS ({ov}).") == []


def test_uniqueness_claims_must_be_true(candidates: list[JoinCandidate]) -> None:
    currency = next(c for c in candidates if (c.from_, c.to) == ("VBAK.WAERK", "BSID.WAERS"))
    ov = currency.evidence_ids[0]
    for claim in (
        "BSID.WAERS is unique",
        "WAERS is unique",
        "BSID.WAERS uniquely identifies rows",
        "The target is a unique key",
        "BSID.WAERS is the primary key",
    ):
        assert "claims BSID.WAERS is unique" in check(currency, f"{claim} ({ov}).")[0], claim
    assert check(currency, f"BSID.WAERS is not unique ({ov}).") == []


def test_every_template_explanation_passes_the_validator(candidates: list[JoinCandidate]) -> None:
    for candidate in candidates:
        assert check(candidate, template_explanation(candidate)) == [], candidate.edge_id


def answers(first: str, second: str) -> FakeProvider:
    """Every edge gets `first` as its explanation, then `second` on the corrective retry."""
    calls = {"n": 0}

    def answer(prompt: Prompt) -> dict[str, Any]:
        calls["n"] += 1
        text = first if calls["n"] == 1 else second
        edge_ids = [line.split(":", 1)[0] for line in prompt.user.splitlines() if line[:1] == "e"]
        return {
            "joins": [
                {"edge_id": e, "include": True, "relevance": "required", "explanation": text}
                for e in edge_ids
            ]
        }

    return FakeProvider().on("rank_joins", answer)


def test_failing_explanations_get_one_retry(candidates: list[JoinCandidate]) -> None:
    fake = answers("Trust me (ov_999).", "Still trust me (ov_998).")
    proposals, warnings = rank_joins(ParsedRequirement(summary="s"), candidates, fake, SETTINGS)
    assert len(fake.calls) == 2
    assert "failed the evidence check" in fake.calls[1].user
    assert all(p.explanation_source == "template" for p in proposals)
    assert any("failed the evidence check" in w for w in warnings)


def test_explanations_fixed_on_retry_are_kept(candidates: list[JoinCandidate]) -> None:
    accepted = [c for c in candidates if c.accepted]

    def answer(prompt: Prompt) -> dict[str, Any]:
        retry = "failed the evidence check" in prompt.user
        joins = []
        for c in accepted:
            explanation = template_explanation(c) if retry else "Trust me (ov_999)."
            joins.append(
                {
                    "edge_id": c.edge_id,
                    "include": True,
                    "relevance": "required",
                    "explanation": explanation,
                }
            )
        return {"joins": joins}

    fake = FakeProvider().on("rank_joins", answer)
    proposals, warnings = rank_joins(ParsedRequirement(summary="s"), candidates, fake, SETTINGS)
    recommended = [p for p in proposals if p.recommended]
    assert len(recommended) == 5
    assert all(p.explanation_source == "llm" for p in recommended)
    assert not any("failed the evidence check" in w for w in warnings)
