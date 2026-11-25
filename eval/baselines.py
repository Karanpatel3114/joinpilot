"""Simple baselines that JoinPilot must beat, using only part of the evidence."""

from __future__ import annotations

from difflib import SequenceMatcher
from itertools import permutations

from eval.join_metrics import PredictedEdge
from joinpilot.joins.names import stem, table_prefix
from joinpilot.profiling.models import ProjectProfile, is_key_like_type

NAME_FUZZY_MIN = 0.8
OVERLAP_MIN = 0.95


def name_only(profile: ProjectProfile) -> list[PredictedEdge]:
    """Join columns whose names match (exactly or fuzzily) and whose types are compatible.

    With no data, the direction is guessed as a person reading the DDL would: the
    target is the column that comes first in its table (usually the primary key).
    When both or neither come first, both directions are predicted.
    """
    columns = []
    for table in profile.tables:
        prefix = table_prefix([c.name for c in table.columns])
        for position, column in enumerate(table.columns):
            if is_key_like_type(column.type):
                columns.append((table.name, column.name, stem(column.name, prefix), position == 0))
    edges = []
    for (ta, ca, sa, first_a), (tb, cb, sb, first_b) in permutations(columns, 2):
        if ta == tb or SequenceMatcher(None, sa, sb).ratio() < NAME_FUZZY_MIN:
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
