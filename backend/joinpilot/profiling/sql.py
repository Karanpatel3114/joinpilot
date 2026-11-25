"""Small helpers for building trusted SQL from server-side names (never user SQL)."""

from __future__ import annotations

from sqlglot import exp


def ident(name: str) -> str:
    """Quote an identifier for DuckDB with sqlglot, so any name is safe to embed."""
    return exp.to_identifier(name, quoted=True).sql(dialect="duckdb")


def column_ref(table: str, column: str) -> str:
    return f"{ident(table)}.{ident(column)}"
