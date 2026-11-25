"""Score candidates, infer cardinality and fan-out risk, and decide which to propose.

The score is a weighted sum of evidence (weights in config). A candidate is accepted
only if its target is unique, it scores above the threshold, it beats the reverse
direction, and it is the best target for its source column.
"""

from __future__ import annotations

import math

from joinpilot.config import JoinSettings
from joinpilot.joins.candidates import ProfileIndex, generate_candidates
from joinpilot.joins.models import Cardinality, JoinCandidate, JoinFilter
from joinpilot.profiling.models import ProjectProfile


def cardinality(candidate: JoinCandidate, unique_min: float) -> Cardinality:
    """N:1 when the target is unique, 1:1 when both sides are, otherwise N:M."""
    if candidate.target_uniqueness < unique_min:
        return "N:M"
    return "1:1" if candidate.source_uniqueness >= unique_min else "N:1"


def raw_score(candidate: JoinCandidate, s: JoinSettings) -> float:
    """Weighted evidence; N:M pairs are damped because they would duplicate rows."""
    distinct = max(candidate.target_distinct, 1)
    strength = min(1.0, math.log(distinct) / math.log(s.key_strength_full_at))
    score = (
        s.weight_inclusion * candidate.inclusion_ratio
        + s.weight_name * candidate.name_similarity
        + s.weight_coverage * candidate.coverage_ratio
        + s.weight_key_strength * strength
    )
    if candidate.cardinality == "N:M":
        score *= s.n_to_m_factor
    return round(min(score, 1.0), 4)


def fan_out(candidate: JoinCandidate, index: ProfileIndex, s: JoinSettings) -> None:
    """Flag attribute tables, such as texts with one row per language, that multiply rows.

    The source table has a two-column key made of the join column and a small
    "discriminator" column, and almost every key has a row for every discriminator
    value. The suggested filter keeps one discriminator value.
    """
    table, column = candidate.from_.split(".", 1)
    distinct = index.columns[candidate.from_].distinct_count
    candidate.rows_per_key = round(index.row_counts[table] / distinct, 4) if distinct else 1.0
    for key in index.composite_keys.get(table, []):
        if column not in key or len(key) != 2:
            continue
        other = f"{table}.{key[1] if key[0] == column else key[0]}"
        d = index.columns[other].distinct_count
        filled = candidate.rows_per_key >= s.discriminator_fill * d
        if 2 <= d <= s.discriminator_max_distinct and filled:
            choices = index.columns[other].sample_values
            preferred = [v for v in s.preferred_filter_values if v in choices]
            candidate.fan_out_risk = True
            candidate.filter = JoinFilter(
                column=other, value=preferred[0] if preferred else choices[0], choices=choices
            )
            composite = index.keys.get((table, tuple(key)))
            if composite:
                candidate.evidence_ids.append(composite.evidence_id)
            return


def decide(candidates: list[JoinCandidate], s: JoinSettings) -> None:
    """Accept the strongest unique-target candidates; record why the others were not."""
    by_pair = {(c.from_, c.to): c for c in candidates}
    for c in candidates:
        reverse = by_pair.get((c.to, c.from_))
        if c.cardinality == "N:M":
            c.rejection_reason = "target values are not unique, so the join would duplicate rows"
        elif c.cardinality == "1:1" and c.name_similarity < 1.0:
            c.rejection_reason = "both columns are unique keys with different names"
        elif c.score < s.accept_threshold:
            c.rejection_reason = "evidence score below the acceptance threshold"
        elif reverse and (reverse.score, reverse.from_) > (c.score, c.from_):
            c.rejection_reason = "the reverse direction is better supported"
        else:
            c.accepted = True
    best: dict[str, JoinCandidate] = {}
    for c in sorted(candidates, key=lambda c: (-c.score, c.to)):
        if c.accepted and c.from_ in best:
            c.accepted = False
            c.rejection_reason = f"{c.from_} already joins {best[c.from_].to} with more evidence"
        elif c.accepted:
            best[c.from_] = c


def score_candidates(profile: ProjectProfile, settings: JoinSettings) -> list[JoinCandidate]:
    """Generate, score and rank all candidates; edge ids follow the ranking (e1 is best)."""
    index = ProfileIndex.build(profile)
    candidates = generate_candidates(profile, settings)
    for c in candidates:
        c.cardinality = cardinality(c, settings.unique_min)
        c.score = raw_score(c, settings)
        fan_out(c, index, settings)
    decide(candidates, settings)
    ranked = sorted(candidates, key=lambda c: (not c.accepted, -c.score, c.from_, c.to))
    for i, c in enumerate(ranked, start=1):
        c.edge_id = f"e{i}"
    return ranked
