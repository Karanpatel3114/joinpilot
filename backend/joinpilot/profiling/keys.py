"""Candidate keys: columns, or pairs of columns, whose values identify every row."""

from __future__ import annotations

from itertools import combinations

import duckdb

from joinpilot.profiling.models import ColumnProfile, is_key_like_type
from joinpilot.profiling.sql import ident


def is_unique_pair(con: duckdb.DuckDBPyConnection, table: str, a: str, b: str) -> bool:
    """True when no (a, b) combination appears on more than one row."""
    row = con.execute(
        f"SELECT COUNT(*) FROM (SELECT 1 FROM {ident(table)} "
        f"GROUP BY {ident(a)}, {ident(b)} HAVING COUNT(*) > 1)"
    ).fetchone()
    return row is not None and int(row[0]) == 0


def candidate_keys(
    con: duckdb.DuckDBPyConnection,
    table: str,
    row_count: int,
    columns: list[ColumnProfile],
    max_pair_columns: int,
) -> list[list[str]]:
    """Single-column keys, or minimal two-column keys when the table has none.

    Pairs are searched only among complete (no nulls) integer or text columns, the
    `max_pair_columns` with the most distinct values, and only when their distinct
    counts could cover every row.
    """
    singles = [[c.name] for c in columns if c.is_key_candidate]
    if singles or row_count == 0:
        return singles
    pool = sorted(
        (
            c
            for c in columns
            if is_key_like_type(c.type) and c.null_pct == 0 and c.distinct_count > 1
        ),
        key=lambda c: -c.distinct_count,
    )[:max_pair_columns]
    order = {c.name: i for i, c in enumerate(columns)}
    pairs = []
    for a, b in combinations(pool, 2):
        if a.distinct_count * b.distinct_count < row_count:
            continue
        if is_unique_pair(con, table, a.name, b.name):
            pairs.append(sorted([a.name, b.name], key=order.__getitem__))
    return sorted(pairs, key=lambda p: (order[p[0]], order[p[1]]))
