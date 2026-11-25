"""Evidence validator: an explanation may only cite this join's evidence, and every
percentage it states must match a number in that evidence (D-002)."""

from __future__ import annotations

import re

from joinpilot.joins.models import JoinCandidate

EVIDENCE_ID = re.compile(r"\b(?:ov|uk)_\d{3,}\b")
PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def evidence_percentages(candidate: JoinCandidate) -> list[float]:
    """Every ratio in the candidate's evidence, as a percentage."""
    ratios = [
        candidate.inclusion_ratio,
        candidate.coverage_ratio,
        candidate.target_uniqueness,
        candidate.source_uniqueness,
        candidate.score,
    ]
    return [round(r * 100, 4) for r in ratios]


def claims_target_unique(candidate: JoinCandidate, explanation: str) -> bool:
    """True for a positive claim such as "KNA1.KUNNR is unique" about the target column.

    "is not unique", "is only 50.0% unique" and claims about other columns do not count.
    """
    subject = re.escape(candidate.to)
    return bool(re.search(rf"{subject}\s+(?:is|are)\s+unique\b", explanation, re.IGNORECASE))


def check_explanation(
    candidate: JoinCandidate,
    explanation: str,
    cited_ids: list[str],
    unique_min: float,
    tolerance_points: float,
) -> list[str]:
    """Return the problems with one explanation; an empty list means it is grounded."""
    problems = []
    allowed = set(candidate.evidence_ids)
    cited = set(cited_ids) | set(EVIDENCE_ID.findall(explanation))
    for evidence_id in sorted(cited - allowed):
        problems.append(f"cites {evidence_id}, which is not evidence for {candidate.edge_id}")
    if not cited & allowed:
        problems.append("cites no evidence id")
    known = evidence_percentages(candidate)
    for match in PERCENT.findall(explanation):
        value = float(match)
        if not any(abs(value - k) <= tolerance_points for k in known):
            problems.append(f"states {match}%, which matches no evidence number")
    if claims_target_unique(candidate, explanation) and candidate.target_uniqueness < unique_min:
        problems.append(
            f"claims uniqueness, but {candidate.to} is only "
            f"{candidate.target_uniqueness:.1%} unique"
        )
    return problems
