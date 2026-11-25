"""Rank and explain join candidates. The model only ranks and explains what profiling
found; it can never add a join or recommend one whose target is not unique (D-002)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from joinpilot.agent.requirement import ParsedRequirement
from joinpilot.agent.validator import check_explanation
from joinpilot.config import AgentSettings
from joinpilot.errors import LLMUnavailableError
from joinpilot.joins.models import Cardinality, JoinCandidate, JoinFilter
from joinpilot.joins.scoring import LOW_SCORE_REASON
from joinpilot.llm.prompts import load_prompt, snippet
from joinpilot.llm.provider import LLMProvider, Prompt
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
    rescued: bool = False
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


def can_rescue(c: JoinCandidate, settings: AgentSettings) -> bool:
    """A rejected candidate the model may still recommend (D-020).

    Only when the scorer's sole objection was a low score: never past a uniqueness,
    1:1 or best-target rule, and never below `rescue_min_score`.
    """
    return (
        c.rejection_reason == LOW_SCORE_REASON
        and c.cardinality in JOINABLE
        and c.score >= settings.rescue_min_score
    )


def to_proposal(c: JoinCandidate, ranked: RankedJoin | None, settings: AgentSettings) -> Proposal:
    """Combine the deterministic decision with the model's view, within the hard rules.

    `ranked` is None when the model did not give a usable, grounded answer for this
    edge; then the scorer decides and the template explains.
    """
    relevance: Relevance
    source: Literal["llm", "template"]
    rescued = False
    if ranked is None:
        recommended, relevance = c.accepted, ("required" if c.accepted else "not_needed")
        explanation, source = template_explanation(c), "template"
    else:
        rescued = ranked.include and not c.accepted and can_rescue(c, settings)
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
        rescued=rescued,
        rejection_reason=c.rejection_reason,
    )


def grounding_problems(
    ranked: dict[str, RankedJoin],
    by_edge: dict[str, JoinCandidate],
    settings: AgentSettings,
    unique_min: float,
) -> dict[str, list[str]]:
    """Evidence problems per edge; edges without problems are left out."""
    problems = {}
    for edge_id, r in ranked.items():
        found = check_explanation(
            by_edge[edge_id],
            r.explanation,
            r.evidence_ids,
            unique_min,
            settings.explanation_tolerance_points,
        )
        if found:
            problems[edge_id] = found
    return problems


@dataclass
class RankingOutcome:
    """Proposals plus what happened on the way, for warnings and evaluation."""

    proposals: list[Proposal]
    warnings: list[str] = field(default_factory=list)
    model_used: bool = False
    failed_checks: int = 0
    omitted: int = 0

    @property
    def stats(self) -> dict[str, int | bool]:
        """Counts an evaluation reports next to the metrics."""
        return {
            "model_used": self.model_used,
            "model_explained": sum(p.explanation_source == "llm" for p in self.proposals),
            "templated": sum(p.explanation_source == "template" for p in self.proposals),
            "failed_checks": self.failed_checks,
            "omitted": self.omitted,
            "rescued": sum(p.rescued for p in self.proposals),
        }


def ask_model(
    llm: LLMProvider,
    prompt: Prompt,
    by_edge: dict[str, JoinCandidate],
    settings: AgentSettings,
    unique_min: float,
    outcome: RankingOutcome,
) -> dict[str, RankedJoin]:
    """Get grounded rankings: one try, one corrective retry, then drop what still fails."""
    draft = llm.generate(prompt, RankingDraft).value
    outcome.model_used = True
    seen: set[str] = set()
    for r in draft.joins:
        if r.edge_id not in by_edge:
            outcome.warnings.append(
                f"The model referred to an unknown join {r.edge_id}; it was ignored."
            )
        elif r.edge_id in seen:
            outcome.warnings.append(
                f"The model ranked {r.edge_id} twice; the first answer is used."
            )
        seen.add(r.edge_id)
    ranked: dict[str, RankedJoin] = {}
    for r in draft.joins:
        if r.edge_id in by_edge:
            ranked.setdefault(r.edge_id, r)
    problems = grounding_problems(ranked, by_edge, settings, unique_min)
    if problems:
        feedback = "\n".join(f"- {e}: {'; '.join(p)}" for e, p in sorted(problems.items()))
        retry = replace(
            prompt, user=f"{prompt.user}\n\n{snippet('fix_evidence', problems=feedback)}"
        )
        try:
            retried = llm.generate(retry, RankingDraft).value
            ranked |= {r.edge_id: r for r in retried.joins if r.edge_id in problems}
        except (LLMUnavailableError, ValidationError) as error:
            outcome.warnings.append(f"The corrective retry failed: {error}")
        problems = grounding_problems(ranked, by_edge, settings, unique_min)
    for edge_id, found in sorted(problems.items()):
        del ranked[edge_id]
        outcome.failed_checks += 1
        outcome.warnings.append(
            f"The explanation for {edge_id} failed the evidence check ({found[0]}); "
            "the scorer's decision and a template explanation are used."
        )
    for edge_id in sorted(set(by_edge) - set(ranked) - set(problems)):
        outcome.omitted += 1
        outcome.warnings.append(f"The model did not rank {edge_id}; the scorer's decision is used.")
    return ranked


def rank_joins(
    requirement: ParsedRequirement,
    candidates: list[JoinCandidate],
    llm: LLMProvider,
    settings: AgentSettings,
    unique_min: float = 0.999,
) -> RankingOutcome:
    """Ask the model to rank and explain the shortlisted candidates; keep it within bounds."""
    short = shortlist(candidates, settings.ranking_max_candidates)
    by_edge = {c.edge_id: c for c in short}
    prompt = load_prompt("rank_joins").render(
        summary=requirement.summary,
        tables=", ".join(requirement.relevant_tables),
        candidates="\n".join(evidence_lines(c) for c in short),
    )
    outcome = RankingOutcome(proposals=[])
    try:
        ranked = ask_model(llm, prompt, by_edge, settings, unique_min, outcome)
    except (LLMUnavailableError, ValidationError) as error:
        message = error.message if isinstance(error, LLMUnavailableError) else "invalid output"
        outcome.warnings.append(f"Deterministic ranking used: {message}")
        ranked = {}
    outcome.proposals = [to_proposal(c, ranked.get(c.edge_id), settings) for c in short]
    for p in outcome.proposals:
        if p.rescued:
            outcome.warnings.append(
                f"The model recommended {p.edge_id}, which scored below the threshold."
            )
    outcome.proposals.sort(key=lambda p: (not p.recommended, -p.score, p.edge_id))
    return outcome
