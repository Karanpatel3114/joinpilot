"""The semantic model a question is answered over: the views, what each column means,
and a few example values, as text for the model (never full rows).

Each view column traces back to a profiled source column: fact columns keep their
name, joined columns are `<TABLE>__<COLUMN>`, parsed text dates end in `_date`, and
the aging columns are derived. Meanings come from SAP-style field hints or readable
names; examples come from the profile.
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
    """One column of a model view and where it comes from."""

    view: str
    name: str
    type: str
    meaning: str
    examples: list[str]


def model_columns(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str, str]]:
    """(view, column, type) for every column of every view in the model schema."""
    rows = con.execute(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = ? ORDER BY table_name, ordinal_position",
        [SANDBOX_SCHEMA],
    ).fetchall()
    return [(str(v), str(c), str(t)) for v, c, t in rows]


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


def meaning_of(table: str, column: ColumnProfile, parsed_date: bool) -> str:
    """Plain words for a source column: its hint, or its readable name."""
    hint = FIELD_HINTS.get(column.name.upper()) or column.name.replace("_", " ")
    where = TABLE_HINTS.get(table.upper(), table.replace("_", " "))
    return f"{hint} ({where})" + (", parsed from YYYYMMDD text" if parsed_date else "")


def describe_columns(
    columns: list[tuple[str, str, str]],
    facts: dict[str, str],
    profile: ProjectProfile,
    kpi: KPISettings,
    example_values: int,
) -> list[ViewColumn]:
    """Meaning and examples for every view column."""
    described = []
    for view, name, type_ in columns:
        examples: list[str] = []
        if name == "aging_bucket":
            meaning, examples = (
                "aging bucket of the open item",
                bucket_labels(kpi.aging_bucket_edges),
            )
        elif name in DERIVED:
            meaning = DERIVED[name]
        else:
            table, column, parsed = source(name, facts.get(view, ""), profile)
            if column is None:
                meaning = name.replace("_", " ")
            else:
                meaning = meaning_of(table, column, parsed)
                examples = [] if parsed else column.sample_values[:example_values]
        described.append(ViewColumn(view, name, type_, meaning, examples))
    return described


def render_model(columns: list[ViewColumn]) -> str:
    """The prompt text: one block per view, one line per column."""
    lines: list[str] = []
    current = None
    for column in columns:
        if column.view != current:
            current = column.view
            lines.append(f'model."{column.view}":')
        examples = f" e.g. {', '.join(column.examples)}" if column.examples else ""
        lines.append(f'  "{column.name}" {column.type}: {column.meaning}.{examples}')
    return "\n".join(lines)
