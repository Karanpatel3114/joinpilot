"""Inclusion scores: what share of one column's values also appear in another column.

All key-like columns are stacked into one "long" table of distinct values, and a
single self-join counts the matches for every pair of columns at once. Source
columns with many distinct values are sampled (deterministically) for speed.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from joinpilot.profiling.models import ColumnProfile, is_key_like_type
from joinpilot.profiling.sql import ident

# Ways to compare values. M2.5 adds normalizing variants.
VARIANTS: dict[str, str] = {"none": "v"}


@dataclass(frozen=True)
class ColumnRef:
    """A column to compare, with its profile."""

    table: str
    profile: ColumnProfile

    @property
    def qualified(self) -> str:
        """`TABLE.COLUMN`, as used in evidence and the API."""
        return f"{self.table}.{self.profile.name}"


@dataclass(frozen=True)
class PairCounts:
    """How many checked source values matched the target, per comparison variant."""

    source: ColumnRef
    target: ColumnRef
    checked: int
    matched: dict[str, int]
    sampled: bool

    def ratio(self, variant: str) -> float:
        """Share of checked source values that matched under `variant`."""
        return self.matched.get(variant, 0) / self.checked if self.checked else 0.0


def overlap_columns(
    tables: dict[str, list[ColumnProfile]], max_value_length: int
) -> list[ColumnRef]:
    """Columns worth comparing: integer or short text columns with at least one value."""
    return [
        ColumnRef(table, column)
        for table, columns in tables.items()
        for column in columns
        if is_key_like_type(column.type)
        and column.distinct_count > 0
        and (column.max_length or 0) <= max_value_length
    ]


def pair_counts(
    con: duckdb.DuckDBPyConnection, refs: list[ColumnRef], sample_size: int
) -> list[PairCounts]:
    """Count matched distinct values for every ordered pair of columns in different tables."""
    if not refs:
        return []
    variant_columns = ", ".join(f"{expr} AS {name}" for name, expr in VARIANTS.items())
    table_index = {table: i for i, table in enumerate(sorted({r.table for r in refs}))}
    selects = [
        f"SELECT DISTINCT {i} AS col, {table_index[ref.table]} AS t, "
        f"CAST({ident(ref.profile.name)} AS VARCHAR) AS v "
        f"FROM {ident(ref.table)} WHERE {ident(ref.profile.name)} IS NOT NULL"
        for i, ref in enumerate(refs)
    ]
    con.execute(
        f"CREATE OR REPLACE TEMP TABLE __jp_values AS SELECT col, t, v, {variant_columns} "
        f"FROM ({' UNION ALL '.join(selects)})"
    )
    con.execute(
        "CREATE OR REPLACE TEMP TABLE __jp_sample AS SELECT * FROM __jp_values "
        "QUALIFY row_number() OVER (PARTITION BY col ORDER BY hash(v), v) <= ?",
        [sample_size],
    )
    try:
        checked = dict(con.execute("SELECT col, COUNT(*) FROM __jp_sample GROUP BY col").fetchall())
        matched: dict[tuple[int, int], dict[str, int]] = {}
        for name in VARIANTS:
            rows = con.execute(
                f"SELECT s.col, f.col, COUNT(DISTINCT s.v) FROM __jp_sample s "
                f"JOIN __jp_values f ON s.{name} = f.{name} AND s.t <> f.t GROUP BY 1, 2"
            ).fetchall()
            for source, target, count in rows:
                matched.setdefault((int(source), int(target)), {})[name] = int(count)
    finally:
        con.execute("DROP TABLE IF EXISTS __jp_sample")
        con.execute("DROP TABLE IF EXISTS __jp_values")
    return [
        PairCounts(
            source=refs[s],
            target=refs[t],
            checked=int(checked[s]),
            matched=counts,
            sampled=refs[s].profile.distinct_count > int(checked[s]),
        )
        for (s, t), counts in sorted(matched.items())
    ]
