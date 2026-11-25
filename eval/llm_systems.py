"""Systems that use a language model, for the comparison in docs/eval-plan.md.

- llm_only: the ablation. The model sees only table and column names and types,
  with no profiling evidence, and lists joins itself.
- joinpilot_full: the real agent steps (requirement parsing, then ranking and
  explaining the deterministic candidates); its recommended joins are scored.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from eval.join_metrics import PredictedEdge
from joinpilot.agent.ranking import rank_joins
from joinpilot.agent.requirement import parse_requirement
from joinpilot.config import Settings
from joinpilot.joins.scoring import score_candidates
from joinpilot.llm.prompts import load_prompt
from joinpilot.llm.provider import LLMProvider
from joinpilot.profiling.models import ProjectProfile

# One requirement per schema that needs every true join, so recall is comparable.
ERP_REQUIREMENT = (
    "Open receivables by customer and aging bucket, 2026 revenue by product group with "
    "product descriptions, monthly order counts, and the top customers by revenue."
)
TPCH_REQUIREMENT = (
    "Revenue from order line items by customer nation and region, by part and by supplier "
    "nation, using the parts each supplier stocks."
)


def requirement_for(dataset_id: str) -> str:
    """The evaluation requirement for a dataset's schema."""
    return TPCH_REQUIREMENT if dataset_id.startswith("tpch") else ERP_REQUIREMENT


class ProposedJoin(BaseModel):
    """One join the LLM-only ablation lists."""

    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str


class ProposedJoins(BaseModel):
    """The LLM-only ablation's answer."""

    joins: list[ProposedJoin]


def schema_text(profile: ProjectProfile) -> str:
    """Names and types only: no counts, overlaps or example values."""
    return "\n".join(
        f"- {t.name}: " + ", ".join(f"{c.name} {c.type}" for c in t.columns) for t in profile.tables
    )


def llm_only(profile: ProjectProfile, llm: LLMProvider) -> list[PredictedEdge]:
    """Joins the model lists from the schema alone; unknown columns are dropped.

    Raises LLMUnavailableError when the model fails; the caller scores that dataset
    as an empty prediction, so its gold joins stay in the denominator.
    """
    prompt = load_prompt("llm_only_joins").render(tables=schema_text(profile))
    known = {
        f"{t.name}.{c.name}".casefold(): f"{t.name}.{c.name}"
        for t in profile.tables
        for c in t.columns
    }
    edges = []
    for join in llm.generate(prompt, ProposedJoins).value.joins:
        source, target = known.get(join.from_.casefold()), known.get(join.to.casefold())
        if source and target and source != target:
            edges.append(PredictedEdge(source, target))
    return edges


def joinpilot_full(
    profile: ProjectProfile, llm: LLMProvider, settings: Settings, requirement: str
) -> tuple[list[PredictedEdge], dict[str, Any]]:
    """The agent's recommended joins, plus what the model actually did.

    The diagnostics show whether parsing fell back to keywords and how many
    explanations were grounded, templated, failed, omitted or rescued, so a model
    failure can never pass as the scorer's numbers.
    """
    parsed, parse_warnings = parse_requirement(requirement, profile, llm, settings.agent)
    candidates = score_candidates(profile, settings.joins)
    outcome = rank_joins(parsed, candidates, llm, settings.agent, settings.joins.unique_min)
    edges = [
        PredictedEdge(
            p.from_,
            p.to,
            p.normalization,
            p.fan_out_risk,
            (p.filter.column, p.filter.value) if p.filter else None,
        )
        for p in outcome.proposals
        if p.recommended
    ]
    diagnostics = {
        "parse_source": parsed.source,
        **outcome.stats,
        "warnings": len(parse_warnings) + len(outcome.warnings),
    }
    return edges, diagnostics
