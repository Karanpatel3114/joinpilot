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


def profile_columns(
    con: duckdb.DuckDBPyConnection, table: str, sample_values: int
) -> tuple[int, list[ColumnProfile]]:
    """Return the row count and one `ColumnProfile` per column."""
    columns = table_columns(con, table)
    parts = ["COUNT(*)"]
    for name, _ in columns:
        c, text = ident(name), f"CAST({ident(name)} AS VARCHAR)"
        parts += [
            f"COUNT({c})",
            f"COUNT(DISTINCT {c})",
            f"CAST(MIN({c}) AS VARCHAR)",
            f"CAST(MAX({c}) AS VARCHAR)",
            f"MIN(length({text}))",
            f"MAX(length({text}))",
            f"COUNT(*) FILTER (WHERE regexp_full_match({text}, '[0-9]+'))",
        ]
    row = con.execute(f"SELECT {', '.join(parts)} FROM {ident(table)}").fetchone()
    assert row is not None
    row_count = int(row[0])
    profiles = []
    for i, (name, data_type) in enumerate(columns):
        start = 1 + AGGREGATES_PER_COLUMN * i
        non_null, distinct, low, high, min_len, max_len, digits = row[
            start : start + AGGREGATES_PER_COLUMN
        ]
        non_null, distinct = int(non_null), int(distinct)
        profiles.append(
            ColumnProfile(
                name=name,
                type=data_type,
                null_pct=round(1 - non_null / row_count, 6) if row_count else 0.0,
                distinct_count=distinct,
                sample_values=first_values(con, table, name, sample_values),
                is_key_candidate=(
                    is_key_like_type(data_type) and row_count > 0 and distinct == row_count
                ),
                min_value=low,
                max_value=high,
                max_length=max_len,
                fixed_length=min_len if non_null and min_len == max_len else None,
                digits_only=non_null > 0 and int(digits) == non_null,
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
