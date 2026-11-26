"""Export the approved model to other warehouses' SQL dialects with sqlglot.

Views are generated for DuckDB; teams usually run them in Postgres, Snowflake or
BigQuery. DuckDB-only functions are rewritten to sqlglot's typed equivalents first
(for example `try_strptime` becomes a safe date parse), and anything a dialect
cannot express is reported next to the SQL instead of failing silently.
"""

from __future__ import annotations

from typing import Any, Literal, get_args

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel, UnsupportedError

Dialect = Literal["duckdb", "postgres", "snowflake", "bigquery"]
DIALECTS: tuple[str, ...] = get_args(Dialect)
POSTGRES_DATES = (
    "Postgres has no safe date parsing: TO_TIMESTAMP fails on malformed YYYYMMDD text, "
    "where DuckDB returns NULL."
)


def portable(node: exp.Expression) -> exp.Expression:
    """Replace DuckDB-only functions with typed nodes every dialect can render."""
    if isinstance(node, exp.Anonymous) and str(node.name).lower() == "try_strptime":
        value, fmt = node.expressions
        return exp.StrToTime(this=value, format=fmt, safe=True)
    return node


def export_sql(sql: str, dialect: Dialect) -> tuple[str, list[str]]:
    """The statement in `dialect`, with notes about anything that may need a manual change."""
    if dialect == "duckdb":
        return sql, []
    tree = sqlglot.parse_one(sql, read="duckdb").transform(portable)
    notes = []
    try:
        out = tree.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE, pretty=True)
    except UnsupportedError as error:
        out = tree.sql(dialect=dialect, unsupported_level=ErrorLevel.IGNORE, pretty=True)
        notes.append(f"Some parts may need a manual change: {error}")
    if dialect == "postgres" and tree.find(exp.StrToTime):
        notes.append(POSTGRES_DATES)
    return out, notes


def export_views(views: list[dict[str, Any]], dialect: Dialect) -> list[dict[str, Any]]:
    """Views with their SQL in `dialect`; notes go into `message` (failed views unchanged)."""
    exported = []
    for view in views:
        if view.get("status") == "failed" or dialect == "duckdb":
            exported.append(view)
            continue
        sql, notes = export_sql(view["sql"], dialect)
        exported.append(
            {**view, "sql": sql, "dialect": dialect, "message": " ".join(notes) or None}
        )
    return exported


def export_script(views: list[dict[str, Any]], dialect: Dialect, run_id: str) -> str:
    """All views of a run as one SQL script, in dependency-free order."""
    parts = [
        f"-- JoinPilot data model for run {run_id}, {dialect} dialect",
        "-- Generated from approved joins; see the run's check results before deploying.",
    ]
    for view in export_views(views, dialect):
        if view.get("status") == "failed":
            continue
        if view.get("message"):
            note = " ".join(str(view["message"]).split())
            parts.append(f"-- Note: {note}")
        parts.append(view["sql"].rstrip(";") + ";")
    return "\n\n".join(parts) + "\n"
