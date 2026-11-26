"""The semantic model a question is answered over, as text for the model (never rows).

First the tested views of the newest model: each keeps every row of one fact table,
with joined columns named `<TABLE>__<COLUMN>`, parsed text dates ending in `_date`
and derived aging columns. Then the raw tables, for questions about one table's own
records (how many customers are in a country), which the fact views cannot count.
Meanings come from SAP-style field hints or readable names; examples from the profile.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from joinpilot.config import KPISettings
from joinpilot.glossary.hints import FIELD_HINTS, TABLE_HINTS
from joinpilot.profiling.models import ColumnProfile, ProjectProfile
from joinpilot.sqlgen.guard import SANDBOX_SCHEMA
from joinpilot.sqlgen.views import bucket_labels

DERIVED = {
    "due_date": "due date of the open item (baseline date plus payment days)",
    "days_overdue": "days past the due date as of the reference date (0 or less: not due)",
}


@dataclass(frozen=True)
class ViewColumn:
    """One column of a model view or raw table, and what it means."""

    schema: str
    view: str
    name: str
    type: str
    meaning: str
    examples: list[str]


def model_columns(
    con: duckdb.DuckDBPyConnection, views: set[str]
) -> list[tuple[str, str, str, str]]:
    """(schema, relation, column, type): the given model views, then every raw table."""
    rows = con.execute(
        "SELECT c.table_schema, c.table_name, c.column_name, c.data_type "
        "FROM information_schema.columns c JOIN information_schema.tables t "
        "ON t.table_schema = c.table_schema AND t.table_name = c.table_name "
        "WHERE (c.table_schema = ? AND t.table_type = 'VIEW') "
        "OR (c.table_schema = 'main' AND t.table_type = 'BASE TABLE') "
        "ORDER BY c.table_schema = 'main', c.table_name, c.ordinal_position",
        [SANDBOX_SCHEMA],
    ).fetchall()
    return [
        (str(s), str(r), str(c), str(t)) for s, r, c, t in rows if s != SANDBOX_SCHEMA or r in views
    ]


def relation_sql(schema: str, relation: str) -> str:
    """How the prompt and the SQL name a relation: model views qualified, raw tables bare."""
    return f'model."{relation}"' if schema == SANDBOX_SCHEMA else f'"{relation}"'


def source(
    view_column: str, fact: str, profile: ProjectProfile
) -> tuple[str, ColumnProfile | None, bool]:
    """The source table, its profiled column (if any) and whether this is a parsed date."""
    table, name = view_column.split("__", 1) if "__" in view_column else (fact, view_column)
    columns = {c.name: c for t in profile.tables if t.name == table for c in t.columns}
    if name in columns:
        return table, columns[name], False
    if name.endswith("_date") and name[: -len("_date")] in columns:
        return table, columns[name[: -len("_date")]], True
    return table, None, False


def source_table(
    table: str, name: str, profile: ProjectProfile
) -> tuple[str, ColumnProfile | None, bool]:
    """A raw table column's own profile."""
    columns = {c.name: c for t in profile.tables if t.name == table for c in t.columns}
    return table, columns.get(name), False


def meaning_of(table: str, column: ColumnProfile, parsed_date: bool) -> str:
    """Plain words for a source column: its hint, or its readable name."""
    hint = FIELD_HINTS.get(column.name.upper()) or column.name.replace("_", " ")
    where = TABLE_HINTS.get(table.upper(), table.replace("_", " "))
    return f"{hint} ({where})" + (", parsed from YYYYMMDD text" if parsed_date else "")


def describe_columns(
    columns: list[tuple[str, str, str, str]],
    facts: dict[str, str],
    profile: ProjectProfile,
    kpi: KPISettings,
    example_values: int,
) -> list[ViewColumn]:
    """Meaning and examples for every view column."""
    described = []
    for schema, view, name, type_ in columns:
        examples: list[str] = []
        derived = schema == SANDBOX_SCHEMA
        if derived and name == "aging_bucket":
            meaning, examples = (
                "aging bucket of the open item",
                bucket_labels(kpi.aging_bucket_edges),
            )
        elif derived and name in DERIVED:
            meaning = DERIVED[name]
        else:
            if schema == SANDBOX_SCHEMA:
                table, column, parsed = source(name, facts.get(view, ""), profile)
            else:
                table, column, parsed = source_table(view, name, profile)
            if column is None:
                meaning = name.replace("_", " ")
            else:
                meaning = meaning_of(table, column, parsed)
                examples = [] if parsed else column.sample_values[:example_values]
        described.append(ViewColumn(schema, view, name, type_, meaning, examples))
    return described


def render_model(columns: list[ViewColumn]) -> str:
    """The prompt text: one block per view, one line per column."""
    lines: list[str] = ["Tested model views (prefer these; their joins are approved and checked):"]
    current: tuple[str, str] | None = None
    for column in columns:
        if (column.schema, column.view) != current:
            if column.schema != SANDBOX_SCHEMA and (
                current is None or current[0] == SANDBOX_SCHEMA
            ):
                lines.append("Raw tables (only for questions about one table's own records):")
            current = (column.schema, column.view)
            lines.append(f"{relation_sql(column.schema, column.view)}:")
        examples = f" e.g. {', '.join(column.examples)}" if column.examples else ""
        lines.append(f'  "{column.name}" {column.type}: {column.meaning}.{examples}')
    return "\n".join(lines)
