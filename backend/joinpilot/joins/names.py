"""Column-name similarity, robust to per-table prefixes such as TPC-H's `l_` and `o_`."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

PREFIX_SHARE = 0.8
FUZZY_WEIGHT = 0.5


def table_prefix(columns: list[str]) -> str:
    """A prefix like `l_` shared by most of a table's columns, or an empty string."""
    prefixes = [c.split("_", 1)[0] + "_" for c in columns if "_" in c]
    if not prefixes or len(columns) < 2:
        return ""
    most_common = max(set(prefixes), key=prefixes.count)
    if prefixes.count(most_common) / len(columns) >= PREFIX_SHARE and len(most_common) <= 4:
        return most_common
    return ""


def stem(column: str, prefix: str) -> str:
    """Lower-case name without the table prefix and separators: `o_custkey` -> `custkey`."""
    name = column[len(prefix) :] if prefix and column.startswith(prefix) else column
    return re.sub(r"[^a-z0-9]", "", name.lower())


def name_similarity(a: str, b: str) -> float:
    """1.0 for equal stems, otherwise half of the character-sequence similarity."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return round(FUZZY_WEIGHT * SequenceMatcher(None, a, b).ratio(), 6)
