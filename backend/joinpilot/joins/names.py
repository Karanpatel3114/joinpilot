"""Column-name similarity.

Two adjustments make names comparable across schemas: per-table prefixes such as
TPC-H's `o_` are stripped, and generic key names such as `id` are qualified with
their (singular) table name, so `customers.id` compares as `customerid`, the same
as `orders.customer_id`.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

GENERIC_KEY_STEMS = frozenset({"id", "key", "code", "no", "nr", "num", "number"})


def table_prefix(columns: list[str], min_share: float, max_length: int) -> str:
    """A prefix like `l_` shared by most of a table's columns, or an empty string."""
    prefixes = [c.split("_", 1)[0] + "_" for c in columns if "_" in c]
    if not prefixes or len(columns) < 2:
        return ""
    most_common = max(sorted(set(prefixes)), key=prefixes.count)
    if prefixes.count(most_common) / len(columns) >= min_share and len(most_common) <= max_length:
        return most_common
    return ""


def singular(table: str) -> str:
    """A rough singular of a table name: `customers` -> `customer`, `categories` -> `category`."""
    name = re.sub(r"[^a-z0-9]", "", table.lower())
    if name.endswith("ies"):
        return name[:-3] + "y"
    if name.endswith(("ses", "xes", "ches", "shes")):
        return name[:-2]
    if name.endswith("s") and not name.endswith("ss"):
        return name[:-1]
    return name


def stem(column: str, prefix: str, table: str = "") -> str:
    """Comparable name: lower case, no table prefix or separators, generic keys qualified."""
    name = column[len(prefix) :] if prefix and column.startswith(prefix) else column
    base = re.sub(r"[^a-z0-9]", "", name.lower())
    return singular(table) + base if table and base in GENERIC_KEY_STEMS else base


def name_similarity(a: str, b: str, fuzzy_weight: float) -> float:
    """1.0 for equal stems, otherwise `fuzzy_weight` times the character-sequence similarity."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return round(fuzzy_weight * SequenceMatcher(None, a, b).ratio(), 6)
