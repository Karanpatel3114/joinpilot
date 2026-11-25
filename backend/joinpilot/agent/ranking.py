"""Rank and explain join candidates. The model only ranks and explains what profiling
found; it can never add a join or recommend one whose target is not unique (D-002)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from joinpilot.agent.prompts import load_prompt
from joinpilot.agent.requirement import ParsedRequirement
from joinpilot.config import AgentSettings
from joinpilot.errors import LLMUnavailableError
from joinpilot.joins.models import Cardinality, JoinCandidate, JoinFilter
from joinpilot.llm.provider import LLMProvider
from joinpilot.profiling.normalize import LPAD_PREFIX

Relevance = Literal["required", "useful", "not_needed"]
JOINABLE: tuple[Cardinality, ...] = ("N:1", "1:1")


class RankedJoin(BaseModel):
    """The model's view of one candidate."""

    edge_id: str
    include: bool
    relevance: Relevance
    explanation: str
    evidence_ids: list[str] = Field(default_factory=list)


class RankingDraft(BaseModel):
    """What the model returns for a list of candidates."""

    joins: list[RankedJoin]


class Proposal(BaseModel):
    """A join the person reviews: evidence, explanation and recommendation."""

    model_config = ConfigDict(populate_by_name=True)

    edge_id: str
    from_: str = Field(alias="from")
    to: str
    cardinality: Cardinality
    normalization: str
    fan_out_risk: bool
    filter: JoinFilter | None = None
    score: float
    evidence_ids: list[str]
    explanation: str
    explanation_source: Literal["llm", "template"]
    relevance: Relevance
    recommended: bool
    status: Literal["proposed", "approved", "rejected"] = "proposed"
    rejection_reason: str | None = None


def pct(ratio: float) -> str:
    """A ratio as a percentage with one decimal, the format explanations use."""
    return f"{ratio * 100:.1f}%"


def normalization_phrase(normalization: str) -> str:
    """Plain words for a recorded normalization."""
    if normalization.startswith(LPAD_PREFIX):
        width = normalization.removeprefix(LPAD_PREFIX)
        return f" after padding them with zeros to {width} characters"
    return {
        "strip_leading_zeros": " after removing leading zeros",
        "trim_upper": " after trimming spaces and ignoring case",
    }.get(normalization, "")


def template_explanation(c: JoinCandidate) -> str:
    """A deterministic explanation built only from the candidate's evidence."""
    roles = c.evidence_roles
    if "inclusion" in roles:
        first = (
            f"{pct(c.inclusion_ratio)} of {c.from_} values appear in {c.to}"
            f"{normalization_phrase(c.normalization)} ({roles['inclusion']})"
        )
    else:
        first = f"{c.from_} and {c.to} have matching names, but their values barely overlap"
    if "target_uniqueness" in roles:
        if c.cardinality in JOINABLE:
            first += f", and {c.to} is unique ({roles['target_uniqueness']})"
        else:
            first += (
                f", but {c.to} is only {pct(c.target_uniqueness)} unique, so the join would "
                f"repeat rows ({roles['target_uniqueness']})"
            )
    text = first + "."
    if c.fan_out_risk and c.filter is not None:
        text += (
            f" Each {c.source_table} key has {c.rows_per_key:g} rows, one per {c.filter.column} "
            f"value, so the join keeps only {c.filter.column} = '{c.filter.value}'"
            + (f" ({roles['fan_out_key']})." if "fan_out_key" in roles else ".")
        )
    if not c.accepted and c.rejection_reason:
        text += f" Not proposed: {c.rejection_reason}."
    return text


def evidence_lines(c: JoinCandidate) -> str:
    """The candidate's facts with their evidence ids, as the model sees them."""
    roles = c.evidence_roles
    facts = []
    if "inclusion" in roles:
        raw = "" if c.normalization == "none" else f" (normalization {c.normalization})"
        facts.append(
            f"{roles['inclusion']}: {pct(c.inclusion_ratio)} of {c.from_} values "
            f"found in {c.to}{raw}"
        )
    if "coverage" in roles:
        facts.append(
            f"{roles['coverage']}: {pct(c.coverage_ratio)} of {c.to} values found in {c.from_}"
        )
    if "target_uniqueness" in roles:
        facts.append(f"{roles['target_uniqueness']}: {c.to} is {pct(c.target_uniqueness)} unique")
    if "source_uniqueness" in roles:
        facts.append(
            f"{roles['source_uniqueness']}: {c.from_} is {pct(c.source_uniqueness)} unique"
        )
    if "fan_out_key" in roles and c.filter is not None:
        facts.append(
            f"{roles['fan_out_key']}: {c.source_table} has {c.rows_per_key:g} rows per key, "
            f"one per {c.filter.column} value; "
            f"suggested filter {c.filter.column} = '{c.filter.value}'"
        )
    decision = "accepted" if c.accepted else f"rejected ({c.rejection_reason})"
    return (
        f"{c.edge_id}: {c.from_} -> {c.to} | {c.cardinality} | score {c.score:.2f}, {decision}\n  "
        + "\n  ".join(facts)
    )


def shortlist(candidates: list[JoinCandidate], limit: int) -> list[JoinCandidate]:
    """Accepted candidates first, then the best of the rest, up to `limit`."""
    accepted = [c for c in candidates if c.accepted]
    others = sorted((c for c in candidates if not c.accepted), key=lambda c: -c.score)
    return (accepted + others)[: max(limit, len(accepted))]


def to_proposal(c: JoinCandidate, ranked: RankedJoin | None, settings: AgentSettings) -> Proposal:
    """Combine the deterministic decision with the model's view, within the hard rules."""
    joinable = c.cardinality in JOINABLE
    relevance: Relevance
    source: Literal["llm", "template"]
    if ranked is None:
        recommended, relevance = c.accepted, ("required" if c.accepted else "not_needed")
        explanation, source = template_explanation(c), "template"
    else:
        rescued = joinable and c.score >= settings.rescue_min_score
        recommended = ranked.include and (c.accepted or rescued)
        relevance, explanation, source = ranked.relevance, ranked.explanation, "llm"
    return Proposal(
        edge_id=c.edge_id,
        from_=c.from_,
        to=c.to,
        cardinality=c.cardinality,
        normalization=c.normalization,
        fan_out_risk=c.fan_out_risk,
        filter=c.filter,
        score=c.score,
        evidence_ids=c.evidence_ids,
        explanation=explanation,
        explanation_source=source,
        relevance=relevance,
        recommended=recommended,
        rejection_reason=c.rejection_reason,
    )


def rank_joins(
    requirement: ParsedRequirement,
    candidates: list[JoinCandidate],
    llm: LLMProvider,
    settings: AgentSettings,
) -> tuple[list[Proposal], list[str]]:
    """Ask the model to rank and explain the shortlisted candidates; keep it within bounds."""
    short = shortlist(candidates, settings.ranking_max_candidates)
    prompt = load_prompt("rank_joins").render(
        summary=requirement.summary,
        tables=", ".join(requirement.relevant_tables),
        candidates="\n".join(evidence_lines(c) for c in short),
    )
    try:
        draft = llm.generate(prompt, RankingDraft).value
    except LLMUnavailableError as error:
        proposals = [to_proposal(c, None, settings) for c in short]
        return proposals, [f"Deterministic ranking used: {error.message}"]
    known = {c.edge_id for c in short}
    ranked = {r.edge_id: r for r in draft.joins if r.edge_id in known}
    warnings = [
        f"The model referred to an unknown join {r.edge_id}; it was ignored."
        for r in draft.joins
        if r.edge_id not in known
    ]
    proposals = [to_proposal(c, ranked.get(c.edge_id), settings) for c in short]
    for p, c in zip(proposals, short, strict=True):
        if p.recommended and not c.accepted:
            warnings.append(f"The model recommended {p.edge_id}, which the scorer had rejected.")
    proposals.sort(key=lambda p: (not p.recommended, -p.score, p.edge_id))
    return proposals, warnings
