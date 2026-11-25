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
from joinpilot.joins.names import singular, stem
from joinpilot.profiling.models import ProjectProfile


def cardinality(candidate: JoinCandidate, unique_min: float) -> Cardinality:
    """From the uniqueness of each side: N:1 (target unique), 1:1, 1:N or N:M."""
    target_unique = candidate.target_uniqueness >= unique_min
    source_unique = candidate.source_uniqueness >= unique_min
    if target_unique:
        return "1:1" if source_unique else "N:1"
    return "1:N" if source_unique else "N:M"


def raw_score(candidate: JoinCandidate, s: JoinSettings) -> float:
    """Weighted evidence; pairs whose target is not unique are damped (they duplicate rows)."""
    distinct = max(candidate.target_distinct, 1)
    strength = min(1.0, math.log(distinct) / math.log(s.key_strength_full_at))
    score = (
        s.weight_inclusion * candidate.inclusion_ratio
        + s.weight_name * candidate.name_similarity
        + s.weight_coverage * candidate.coverage_ratio
        + s.weight_key_strength * strength
    )
    if candidate.cardinality in ("1:N", "N:M"):
        score *= s.n_to_m_factor
    return round(min(score, 1.0), 4)


def fan_out(candidate: JoinCandidate, index: ProfileIndex, s: JoinSettings) -> None:
    """Flag attribute tables, such as texts with one row per language, that multiply rows.

    The source table has a two-column key made of the join column and a small,
    non-numeric "discriminator" column (a code such as a language, never an item
    number), and almost every key has a row for every discriminator value. The
    suggested filter keeps one discriminator value.
    """
    table, column = candidate.from_.split(".", 1)
    distinct = index.columns[candidate.from_].distinct_count
    candidate.rows_per_key = round(index.row_counts[table] / distinct, 4) if distinct else 1.0
    for key in index.composite_keys.get(table, []):
        if column not in key or len(key) != 2:
            continue
        other = f"{table}.{key[1] if key[0] == column else key[0]}"
        profile = index.columns[other]
        d = profile.distinct_count
        is_code = profile.type == "VARCHAR" and not profile.digits_only
        all_values_known = d <= len(profile.sample_values)
        filled = candidate.rows_per_key >= s.discriminator_fill * d
        if is_code and all_values_known and 2 <= d <= s.discriminator_max_distinct and filled:
            choices = profile.sample_values
            preferred = [v for v in s.preferred_filter_values if v in choices]
            candidate.fan_out_risk = True
            candidate.filter = JoinFilter(
                column=other, value=preferred[0] if preferred else choices[0], choices=choices
            )
            composite = index.keys.get((table, tuple(key)))
            if composite:
                candidate.evidence_ids.append(composite.evidence_id)
                candidate.evidence_roles["fan_out_key"] = composite.evidence_id
            return


def rejection_reason(
    c: JoinCandidate, reverse: JoinCandidate | None, s: JoinSettings
) -> str | None:
    """Why a candidate should not be proposed, or None if it may be."""
    if c.cardinality == "N:M":
        return "neither side is unique, so the join would duplicate rows"
    if c.cardinality == "1:N":
        return "only the source side is unique; the join runs the other way (many to one)"
    if c.cardinality == "1:1":
        strong = min(c.inclusion_ratio, c.coverage_ratio) >= s.one_to_one_min_overlap
        if c.name_similarity < 1.0 or not strong:
            return "both columns are unique keys without matching names and full overlap"
    if c.score < s.accept_threshold:
        return "evidence score below the acceptance threshold"
    if reverse and (reverse.score, reverse.from_) > (c.score, c.from_):
        return "the reverse direction is better supported"
    return None


def table_affinity(c: JoinCandidate) -> int:
    """1 when the target table's name is part of the key name (customers / customer_id)."""
    table, column = c.to.split(".", 1)
    return int(singular(table) in stem(column, "", table))


def decide(candidates: list[JoinCandidate], s: JoinSettings) -> None:
    """Accept the strongest unique-target candidates; record why the others were not."""
    by_pair = {(c.from_, c.to): c for c in candidates}
    for c in candidates:
        c.rejection_reason = rejection_reason(c, by_pair.get((c.to, c.from_)), s)
        c.accepted = c.rejection_reason is None
    best: dict[str, JoinCandidate] = {}
    order = sorted(
        candidates,
        key=lambda c: (-c.score, -c.name_similarity, -table_affinity(c), -c.coverage_ratio, c.to),
    )
    for c in order:
        if c.accepted and c.from_ in best:
            c.accepted = False
            c.rejection_reason = (
                f"{c.from_} already joins {best[c.from_].to}, which has at least as much evidence"
            )
        elif c.accepted:
            best[c.from_] = c


def score_candidates(profile: ProjectProfile, settings: JoinSettings) -> list[JoinCandidate]:
    """Generate, score and rank all candidates; edge ids follow the ranking (e1 is best)."""
    index = ProfileIndex.build(profile, settings)
    candidates = generate_candidates(index, settings)
    for c in candidates:
        c.cardinality = cardinality(c, settings.unique_min)
        c.score = raw_score(c, settings)
        fan_out(c, index, settings)
    decide(candidates, settings)
    ranked = sorted(candidates, key=lambda c: (not c.accepted, -c.score, c.from_, c.to))
    for i, c in enumerate(ranked, start=1):
        c.edge_id = f"e{i}"
    return ranked
