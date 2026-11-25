"""Simple baselines that JoinPilot must beat, using only part of the evidence."""

from __future__ import annotations

from difflib import SequenceMatcher
from itertools import permutations

from eval.join_metrics import PredictedEdge
from joinpilot.config import JoinSettings
from joinpilot.joins.names import stem, table_prefix
from joinpilot.profiling.models import INTEGER_TYPES, ProjectProfile, is_key_like_type

NAME_FUZZY_MIN = 0.8
OVERLAP_MIN = 0.95
IND_OVERLAP_MIN = 0.9
IND_UNIQUE_MIN = 0.999


def type_family(data_type: str) -> str:
    """Integer or text: the two families of key types."""
    return "integer" if data_type in INTEGER_TYPES else "text"


def name_only(profile: ProjectProfile) -> list[PredictedEdge]:
    """Join columns whose names match (exactly or fuzzily) and whose type families match.

    With no data, the direction is guessed as a person reading the DDL would: the
    target is the column that comes first in its table (usually the primary key).
    When both or neither come first, both directions are predicted.
    """
    s = JoinSettings()
    columns = []
    for table in profile.tables:
        prefix = table_prefix(
            [c.name for c in table.columns], s.prefix_min_share, s.prefix_max_length
        )
        for position, column in enumerate(table.columns):
            if is_key_like_type(column.type):
                name = stem(column.name, prefix, table.name)
                family = type_family(column.type)
                columns.append((table.name, column.name, name, family, position == 0))
    edges = []
    for (ta, ca, sa, fa, first_a), (tb, cb, sb, fb, first_b) in permutations(columns, 2):
        if ta == tb or fa != fb or SequenceMatcher(None, sa, sb).ratio() < NAME_FUZZY_MIN:
            continue
        if (first_b and not first_a) or first_a == first_b:
            edges.append(PredictedEdge(f"{ta}.{ca}", f"{tb}.{cb}"))
    return edges


def overlap_only(profile: ProjectProfile) -> list[PredictedEdge]:
    """Join every column pair whose values overlap at or above a fixed threshold."""
    return [
        PredictedEdge(o.from_, o.to, normalization=o.normalization)
        for o in profile.overlaps
        if o.inclusion_ratio >= OVERLAP_MIN
    ]


def inclusion_dependency(profile: ProjectProfile) -> list[PredictedEdge]:
    """The textbook foreign-key rule: high overlap into a unique column from a non-unique one.

    No names and no weights: inclusion of at least 90% (after the profile's
    normalization), a unique target and a non-unique source.
    """
    uniqueness = {
        f"{k.table}.{k.columns[0]}": k.uniqueness for k in profile.keys if len(k.columns) == 1
    }
    return [
        PredictedEdge(o.from_, o.to, normalization=o.normalization)
        for o in profile.overlaps
        if o.inclusion_ratio >= IND_OVERLAP_MIN
        and uniqueness.get(o.to, 0.0) >= IND_UNIQUE_MIN
        and uniqueness.get(o.from_, 0.0) < IND_UNIQUE_MIN
    ]
