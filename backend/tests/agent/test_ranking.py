import re
from collections.abc import Callable
from typing import Any

import pytest

from joinpilot.agent.ranking import (
    evidence_lines,
    rank_joins,
    shortlist,
    template_explanation,
)
from joinpilot.agent.requirement import ParsedRequirement
from joinpilot.config import AgentSettings, JoinSettings
from joinpilot.errors import LLMUnavailableError
from joinpilot.joins.models import JoinCandidate
from joinpilot.joins.scoring import score_candidates
from joinpilot.llm.factory import UnavailableProvider
from joinpilot.llm.fake import FakeProvider
from joinpilot.llm.provider import Prompt
from joinpilot.profiling.models import ProjectProfile

REQUIREMENT = ParsedRequirement(summary="Receivables aging and revenue", relevant_tables=["BSID"])
SETTINGS = AgentSettings()


@pytest.fixture
def candidates(sap_profile: ProjectProfile) -> list[JoinCandidate]:
    return score_candidates(sap_profile, JoinSettings())


def by_pair(candidates: list[JoinCandidate], a: str, b: str) -> JoinCandidate:
    return next(c for c in candidates if (c.from_, c.to) == (a, b))


def model(decide: Callable[[str], bool]) -> FakeProvider:
    """A fake model that includes edges by `decide(edge_id)` and cites the ids in the prompt."""

    def answer(prompt: Prompt) -> dict[str, Any]:
        joins = []
        for block in prompt.user.split("\ne")[1:]:
            edge_id = "e" + block.split(":", 1)[0]
            ids = re.findall(r"\b(?:ov|uk)_\d+", block)
            joins.append(
                {
                    "edge_id": edge_id,
                    "include": decide(edge_id),
                    "relevance": "required",
                    "explanation": f"Evidence ({ids[0]}).",
                    "evidence_ids": ids[:1],
                }
            )
        return {"joins": joins}

    return FakeProvider().on("rank_joins", answer)


def test_template_explanations_cite_their_evidence(candidates: list[JoinCandidate]) -> None:
    bsid = by_pair(candidates, "BSID.KUNNR", "KNA1.KUNNR")
    text = template_explanation(bsid)
    assert f"{bsid.inclusion_ratio * 100:.1f}%" in text
    assert "padding them with zeros to 10 characters" in text
    assert bsid.evidence_roles["inclusion"] in text
    assert bsid.evidence_roles["target_uniqueness"] in text
    makt = template_explanation(by_pair(candidates, "MAKT.MATNR", "MARA.MATNR"))
    assert "MAKT.SPRAS = 'E'" in makt and "2 rows" in makt
    currency = template_explanation(by_pair(candidates, "VBAK.WAERK", "BSID.WAERS"))
    assert "repeat rows" in currency and "Not proposed" in currency


def test_without_a_model_the_scorer_decides_and_templates_explain(
    candidates: list[JoinCandidate],
) -> None:
    outcome = rank_joins(REQUIREMENT, candidates, UnavailableProvider("off"), SETTINGS)
    proposals, warnings = outcome.proposals, outcome.warnings
    recommended = {(p.from_, p.to) for p in proposals if p.recommended}
    assert recommended == {(c.from_, c.to) for c in candidates if c.accepted}
    assert all(p.explanation_source == "template" for p in proposals)
    assert proposals[0].recommended
    assert "Deterministic ranking used" in warnings[0]


def test_the_model_may_drop_joins_but_never_add_n_to_m_ones(
    candidates: list[JoinCandidate],
) -> None:
    dropped = by_pair(candidates, "VBAP.MATNR", "MARA.MATNR").edge_id
    proposals = rank_joins(
        REQUIREMENT, candidates, model(lambda e: e != dropped), SETTINGS
    ).proposals
    by_edge = {p.edge_id: p for p in proposals}
    assert not by_edge[dropped].recommended
    currency = by_pair(candidates, "VBAK.WAERK", "BSID.WAERS").edge_id
    if currency in by_edge:
        assert not by_edge[currency].recommended
    assert all(p.cardinality in ("N:1", "1:1") for p in proposals if p.recommended)
    assert all(p.explanation_source == "llm" for p in proposals)


def test_unknown_edges_from_the_model_are_ignored(candidates: list[JoinCandidate]) -> None:
    fake = FakeProvider().on(
        "rank_joins",
        lambda p: {
            "joins": [
                {"edge_id": "e999", "include": True, "relevance": "required", "explanation": "x"}
            ]
        },
    )
    outcome = rank_joins(REQUIREMENT, candidates, fake, SETTINGS)
    proposals, warnings = outcome.proposals, outcome.warnings
    assert all(p.edge_id != "e999" for p in proposals)
    assert "unknown join e999" in warnings[0]


def test_prompt_lists_evidence_and_is_bounded(candidates: list[JoinCandidate]) -> None:
    short = shortlist(candidates, limit=7)
    assert len(short) == 7 and all(c.accepted for c in short[:5])
    lines = evidence_lines(by_pair(candidates, "BSID.KUNNR", "KNA1.KUNNR"))
    assert "lpad_zeros:10" in lines and "unique" in lines


def synthetic(
    edge_id: str, score: float, reason: str | None, cardinality: str = "N:1"
) -> JoinCandidate:
    return JoinCandidate(
        edge_id=edge_id,
        from_=f"A{edge_id}.k",
        to=f"B{edge_id}.k",
        inclusion_ratio=0.8,
        target_uniqueness=1.0,
        score=score,
        cardinality=cardinality,  # type: ignore[arg-type]
        accepted=reason is None,
        rejection_reason=reason,
        evidence_ids=[f"ov_{edge_id[1:]:0>3}"],
        evidence_roles={"inclusion": f"ov_{edge_id[1:]:0>3}"},
    )


def include_all(explanation: Callable[[str], str]) -> FakeProvider:
    def answer(prompt: Prompt) -> dict[str, Any]:
        ids = [line.split(":", 1)[0] for line in prompt.user.splitlines() if line[:1] == "e"]
        return {
            "joins": [
                {
                    "edge_id": e,
                    "include": True,
                    "relevance": "required",
                    "explanation": explanation(e),
                }
                for e in ids
            ]
        }

    return FakeProvider().on("rank_joins", answer)


def grounded(edge_id: str) -> str:
    return f"80.0% of the values match (ov_{edge_id[1:]:0>3})."


def test_only_low_score_rejections_with_grounded_explanations_are_rescued() -> None:
    from joinpilot.joins.scoring import LOW_SCORE_REASON

    candidates = [
        synthetic("e1", 0.55, LOW_SCORE_REASON),
        synthetic("e2", 0.45, LOW_SCORE_REASON),
        synthetic("e3", 0.9, "Ae3.k already joins Bx.k, which has at least as much evidence"),
        synthetic("e4", 0.9, "both columns are unique keys without matching names", "1:1"),
    ]
    outcome = rank_joins(REQUIREMENT, candidates, include_all(grounded), SETTINGS)
    by_edge = {p.edge_id: p for p in outcome.proposals}
    assert by_edge["e1"].recommended and by_edge["e1"].rescued
    assert not by_edge["e2"].recommended
    assert not by_edge["e3"].recommended
    assert not by_edge["e4"].recommended
    assert outcome.stats["rescued"] == 1


def test_a_failed_explanation_cannot_rescue_or_drop_a_join() -> None:
    from joinpilot.joins.scoring import LOW_SCORE_REASON

    candidates = [synthetic("e1", 0.55, LOW_SCORE_REASON), synthetic("e2", 0.95, None)]
    outcome = rank_joins(
        REQUIREMENT, candidates, include_all(lambda e: "Trust me (ov_999)."), SETTINGS
    )
    by_edge = {p.edge_id: p for p in outcome.proposals}
    assert not by_edge["e1"].recommended and not by_edge["e1"].rescued
    assert by_edge["e2"].recommended
    assert all(p.explanation_source == "template" for p in outcome.proposals)
    assert outcome.stats["failed_checks"] == 2


def test_omitted_edges_use_the_scorer_and_are_reported(candidates: list[JoinCandidate]) -> None:
    first = candidates[0].edge_id
    fake = FakeProvider().on(
        "rank_joins",
        lambda p: {
            "joins": [
                {
                    "edge_id": first,
                    "include": True,
                    "relevance": "required",
                    "explanation": template_explanation(candidates[0]),
                }
            ]
        },
    )
    outcome = rank_joins(REQUIREMENT, candidates, fake, SETTINGS)
    assert outcome.stats["omitted"] == len(outcome.proposals) - 1
    assert sum(p.recommended for p in outcome.proposals) == 5


def test_a_failing_retry_keeps_the_good_first_answers(candidates: list[JoinCandidate]) -> None:
    accepted = [c for c in candidates if c.accepted]
    calls = {"n": 0}

    def answer(prompt: Prompt) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] > 1:
            raise LLMUnavailableError("quota", {"status": 429})
        return {
            "joins": [
                {
                    "edge_id": c.edge_id,
                    "include": True,
                    "relevance": "required",
                    "explanation": template_explanation(c) if i else "Bad (ov_999).",
                }
                for i, c in enumerate(accepted)
            ]
        }

    outcome = rank_joins(REQUIREMENT, candidates, FakeProvider().on("rank_joins", answer), SETTINGS)
    sources = {p.edge_id: p.explanation_source for p in outcome.proposals if p.recommended}
    assert sources[accepted[0].edge_id] == "template"
    assert all(sources[c.edge_id] == "llm" for c in accepted[1:])
    assert any("corrective retry failed" in w for w in outcome.warnings)


def test_raw_providers_with_invalid_output_fall_back_cleanly(
    candidates: list[JoinCandidate],
) -> None:
    fake = FakeProvider().on("rank_joins", lambda p: {"joins": "not a list"})
    outcome = rank_joins(REQUIREMENT, candidates, fake, SETTINGS)
    assert not outcome.model_used
    assert "Deterministic ranking used: invalid output" in outcome.warnings[0]
