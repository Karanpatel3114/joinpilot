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
    proposals, warnings = rank_joins(REQUIREMENT, candidates, UnavailableProvider("off"), SETTINGS)
    recommended = {(p.from_, p.to) for p in proposals if p.recommended}
    assert recommended == {(c.from_, c.to) for c in candidates if c.accepted}
    assert all(p.explanation_source == "template" for p in proposals)
    assert proposals[0].recommended
    assert "Deterministic ranking used" in warnings[0]


def test_the_model_may_drop_joins_but_never_add_n_to_m_ones(
    candidates: list[JoinCandidate],
) -> None:
    dropped = by_pair(candidates, "VBAP.MATNR", "MARA.MATNR").edge_id
    proposals, _ = rank_joins(REQUIREMENT, candidates, model(lambda e: e != dropped), SETTINGS)
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
    proposals, warnings = rank_joins(REQUIREMENT, candidates, fake, SETTINGS)
    assert all(p.edge_id != "e999" for p in proposals)
    assert "unknown join e999" in warnings[0]


def test_prompt_lists_evidence_and_is_bounded(candidates: list[JoinCandidate]) -> None:
    short = shortlist(candidates, limit=7)
    assert len(short) == 7 and all(c.accepted for c in short[:5])
    lines = evidence_lines(by_pair(candidates, "BSID.KUNNR", "KNA1.KUNNR"))
    assert "lpad_zeros:10" in lines and "unique" in lines
