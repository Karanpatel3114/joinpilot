"""Candidate joins: every column pair that overlaps enough, or whose names match.

Candidates come only from profiling evidence. Nothing here (or later, in the agent)
may invent a join that is not in this list.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from itertools import permutations

from joinpilot.config import JoinSettings
from joinpilot.joins.models import JoinCandidate
from joinpilot.joins.names import name_similarity, stem, table_prefix
from joinpilot.profiling.models import (
    ColumnProfile,
    KeyEvidence,
    Overlap,
    ProjectProfile,
    is_key_like_type,
)


@dataclass
class ProfileIndex:
    """Fast lookups over a project profile, keyed by `TABLE.COLUMN`."""

    columns: dict[str, ColumnProfile] = field(default_factory=dict)
    row_counts: dict[str, int] = field(default_factory=dict)
    stems: dict[str, str] = field(default_factory=dict)
    overlaps: dict[tuple[str, str], Overlap] = field(default_factory=dict)
    keys: dict[tuple[str, tuple[str, ...]], KeyEvidence] = field(default_factory=dict)
    composite_keys: dict[str, list[list[str]]] = field(default_factory=dict)

    @classmethod
    def build(cls, profile: ProjectProfile, settings: JoinSettings) -> ProfileIndex:
        """Index tables, columns, overlaps and key evidence of a profile."""
        index = cls()
        for table in profile.tables:
            names = [c.name for c in table.columns]
            prefix = table_prefix(names, settings.prefix_min_share, settings.prefix_max_length)
            index.row_counts[table.name] = table.row_count
            index.composite_keys[table.name] = [k for k in table.candidate_keys if len(k) > 1]
            for column in table.columns:
                qualified = f"{table.name}.{column.name}"
                index.columns[qualified] = column
                index.stems[qualified] = stem(column.name, prefix, table.name)
        index.overlaps = {(o.from_, o.to): o for o in profile.overlaps}
        index.keys = {(k.table, tuple(k.columns)): k for k in profile.keys}
        return index

    def uniqueness(self, qualified: str) -> KeyEvidence | None:
        """Uniqueness evidence of one column, if profiling recorded it."""
        table, column = qualified.split(".", 1)
        return self.keys.get((table, (column,)))


def key_like_columns(index: ProfileIndex) -> list[str]:
    """Integer and text columns, the only types that can be join keys."""
    return sorted(q for q, c in index.columns.items() if is_key_like_type(c.type))


def candidate_pairs(index: ProfileIndex, settings: JoinSettings) -> list[tuple[str, str]]:
    """Directed pairs with enough value overlap, plus key-like pairs with equal name stems."""
    pairs = {
        pair
        for pair, o in index.overlaps.items()
        if o.inclusion_ratio >= settings.candidate_min_inclusion
    }
    by_stem: dict[str, list[str]] = defaultdict(list)
    for column in key_like_columns(index):
        by_stem[index.stems[column]].append(column)
    for group in by_stem.values():
        for a, b in permutations(group, 2):
            if a.split(".")[0] != b.split(".")[0]:
                pairs.add((a, b))
    return sorted(pairs)


def build_candidate(
    index: ProfileIndex, source: str, target: str, settings: JoinSettings
) -> JoinCandidate:
    """Collect the evidence features of one directed pair."""
    forward = index.overlaps.get((source, target))
    reverse = index.overlaps.get((target, source))
    target_key = index.uniqueness(target)
    source_key = index.uniqueness(source)
    roles = {
        role: item.evidence_id
        for role, item in (
            ("inclusion", forward),
            ("coverage", reverse),
            ("target_uniqueness", target_key),
            ("source_uniqueness", source_key),
        )
        if item is not None
    }
    return JoinCandidate(
        from_=source,
        to=target,
        normalization=forward.normalization if forward else "none",
        inclusion_ratio=forward.inclusion_ratio if forward else 0.0,
        coverage_ratio=reverse.inclusion_ratio if reverse else 0.0,
        target_uniqueness=target_key.uniqueness if target_key else 0.0,
        source_uniqueness=source_key.uniqueness if source_key else 0.0,
        target_distinct=index.columns[target].distinct_count,
        name_similarity=name_similarity(
            index.stems[source], index.stems[target], settings.name_fuzzy_weight
        ),
        evidence_ids=list(roles.values()),
        evidence_roles=roles,
    )


def generate_candidates(index: ProfileIndex, settings: JoinSettings) -> list[JoinCandidate]:
    """All candidate joins of a project, unscored, in a stable order."""
    return [build_candidate(index, a, b, settings) for a, b in candidate_pairs(index, settings)]
