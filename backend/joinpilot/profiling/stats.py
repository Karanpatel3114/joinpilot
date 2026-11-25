"""Column statistics for one table, computed in a single DuckDB scan."""

from __future__ import annotations

import duckdb

from joinpilot.profiling.models import ColumnProfile, is_key_like_type
from joinpilot.profiling.sql import ident

AGGREGATES_PER_COLUMN = 7


def table_columns(con: duckdb.DuckDBPyConnection, table: str) -> list[tuple[str, str]]:
    """Return (column name, DuckDB type) pairs in table order."""
    rows = con.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'main' AND table_name = ? ORDER BY ordinal_position",
        [table],
    ).fetchall()
    return [(str(name), str(data_type)) for name, data_type in rows]


def column_aggregates(name: str) -> list[str]:
    """The SQL aggregates computed for one column, in a fixed order."""
    c, text = ident(name), f"CAST({ident(name)} AS VARCHAR)"
    return [
        f"COUNT({c})",
        f"COUNT(DISTINCT {c})",
        f"CAST(MIN({c}) AS VARCHAR)",
        f"CAST(MAX({c}) AS VARCHAR)",
        f"MIN(length({text}))",
        f"MAX(length({text}))",
        f"COUNT(*) FILTER (WHERE regexp_full_match({text}, '[0-9]+'))",
    ]


def profile_columns(
    con: duckdb.DuckDBPyConnection, table: str, sample_values: int, batch_size: int = 50
) -> tuple[int, list[ColumnProfile]]:
    """Return the row count and one `ColumnProfile` per column.

    Columns are aggregated `batch_size` at a time, so wide tables never build one
    huge query that holds every column's distinct values in memory at once.
    """
    columns = table_columns(con, table)
    count = con.execute(f"SELECT COUNT(*) FROM {ident(table)}").fetchone()
    row_count = int(count[0]) if count else 0
    values: list[object] = []
    for i in range(0, len(columns), max(batch_size, 1)):
        batch = columns[i : i + max(batch_size, 1)]
        parts = [agg for name, _ in batch for agg in column_aggregates(name)]
        row = con.execute(f"SELECT {', '.join(parts)} FROM {ident(table)}").fetchone()
        assert row is not None
        values.extend(row)
    profiles = []
    for i, (name, data_type) in enumerate(columns):
        start = AGGREGATES_PER_COLUMN * i
        non_null_raw, distinct_raw, low, high, min_len, max_len, digits = values[
            start : start + AGGREGATES_PER_COLUMN
        ]
        non_null, distinct = int(str(non_null_raw)), int(str(distinct_raw))
        profiles.append(
            ColumnProfile(
                name=name,
                type=data_type,
                null_pct=round(1 - non_null / row_count, 6) if row_count else 0.0,
                non_null_count=non_null,
                distinct_count=distinct,
                sample_values=first_values(con, table, name, sample_values),
                is_key_candidate=(
                    is_key_like_type(data_type) and row_count > 0 and distinct == row_count
                ),
                min_value=None if low is None else str(low),
                max_value=None if high is None else str(high),
                max_length=None if max_len is None else int(str(max_len)),
                fixed_length=int(str(min_len)) if non_null and min_len == max_len else None,
                digits_only=non_null > 0 and int(str(digits)) == non_null,
            )
        )
    return row_count, profiles


def first_values(con: duckdb.DuckDBPyConnection, table: str, column: str, k: int) -> list[str]:
    """Up to `k` distinct example values, smallest first, so results are deterministic."""
    text = f"CAST({ident(column)} AS VARCHAR)"
    rows = con.execute(
        f"SELECT DISTINCT {text} AS v FROM {ident(table)} WHERE {ident(column)} IS NOT NULL "
        f"ORDER BY v LIMIT {int(k)}"
    ).fetchall()
    return [str(r[0]) for r in rows]
