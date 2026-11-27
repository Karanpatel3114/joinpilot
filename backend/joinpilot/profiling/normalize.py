"""Key normalization: detect when values only match after cleaning, and record how.

ERP extracts often store the same key differently, for example `0000100023` in the
customer master and `100023` in open items. Profiling compares values raw, without
leading zeros, and trimmed and upper-cased; it keeps a normalization only when it
clearly raises the overlap, and records it so views and checks apply the same rule.
"""

from __future__ import annotations

from typing import Literal

from joinpilot.profiling.models import ColumnProfile
from joinpilot.profiling.overlap import NONE, STRIP_ZEROS, TRIM_UPPER, VARIANTS, PairCounts

LPAD_PREFIX = "lpad_zeros:"


def choose_normalization(pair: PairCounts, min_gain: float) -> tuple[str, float]:
    """Return (normalization label, inclusion ratio) for one column pair.

    `none` wins unless another variant improves the ratio by at least `min_gain`.
    Stripped zeros become `lpad_zeros:N` when the target is fixed-width digits, so
    the view can pad the source side and keep the target's own format.
    """
    raw = pair.ratio(NONE)
    best_name, best_ratio = NONE, raw
    for name in VARIANTS:
        if pair.ratio(name) > best_ratio:
            best_name, best_ratio = name, pair.ratio(name)
    if best_ratio - raw < min_gain:
        return NONE, raw
    if best_name == STRIP_ZEROS and pads_to_target(pair.source.profile, pair.target.profile):
        return f"{LPAD_PREFIX}{pair.target.profile.fixed_length}", best_ratio
    return best_name, best_ratio


def pads_to_target(source: ColumnProfile, target: ColumnProfile) -> bool:
    """True when padding the source with zeros reproduces the target's fixed-width format."""
    return bool(
        target.digits_only
        and target.fixed_length
        and (source.max_length or 0) <= target.fixed_length
    )


def normalized_sql(
    column_sql: str, normalization: str, side: Literal["from", "to"], as_text: bool = False
) -> str:
    """SQL expression that applies a recorded normalization to one side of a join.

    `as_text` compares the raw value as text, the way profiling measured the overlap.
    Joins between columns of different types need it: otherwise DuckDB casts the text
    side to a number, which fails on values like `MAT-X` and matches `0005` to `5`.
    """
    text = f"CAST({column_sql} AS VARCHAR)"
    raw = text if as_text else column_sql
    if normalization == NONE:
        return raw
    if normalization.startswith(LPAD_PREFIX):
        width = int(normalization.removeprefix(LPAD_PREFIX))
        return f"lpad({text}, {width}, '0')" if side == "from" else raw
    if normalization == STRIP_ZEROS:
        return f"ltrim({text}, '0')"
    if normalization == TRIM_UPPER:
        return f"upper(trim({text}))"
    raise ValueError(f"unknown normalization: {normalization}")
