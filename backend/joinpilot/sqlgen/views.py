"""Generate SQL views from approved joins (deterministic; the guard checks every view).

One view per fact table: the fact (a table that approved joins start from but
that no approved join points to) left-joined along approved joins to its
dimensions, so every fact row is kept exactly once. Attribute tables with a
fan-out filter (such as texts per language) are attached to their dimension with
that filter. Derived columns fix common ERP habits: YYYYMMDD text dates become
DATE columns, and receivables get a due date, days overdue and an aging bucket
when the requirement asks for aging.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

import duckdb
from pydantic import BaseModel, Field
from sqlglot import exp

from joinpilot.config import KPISettings
from joinpilot.glossary.hints import FIELD_HINTS
from joinpilot.profiling.models import ColumnProfile, ProjectProfile
from joinpilot.profiling.normalize import normalized_sql
from joinpilot.profiling.sql import ident
from joinpilot.sqlgen.guard import (
    SANDBOX_SCHEMA,
    UnsafeSQLError,
    catalog_from_connection,
    guard_sql,
)

AGING_WORDS = ("aging", "ageing", "overdue", "receivable", "due date", "past due")


@dataclass(frozen=True)
class ApprovedJoin:
    """An approved join with what the view needs from its proposal."""

    edge_id: str
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    normalization: str = "none"
    filter_column: str | None = None
    filter_value: str | None = None

    @classmethod
    def from_proposal(cls, proposal: dict[str, Any]) -> ApprovedJoin:
        """Build from a stored proposal (`from`/`to` are TABLE.COLUMN)."""
        source_table, source_column = proposal["from"].split(".", 1)
        target_table, target_column = proposal["to"].split(".", 1)
        flt = proposal.get("filter") or {}
        column = flt.get("column", "").split(".", 1)[-1] or None
        return cls(
            proposal["edge_id"],
            source_table,
            source_column,
            target_table,
            target_column,
            proposal.get("normalization", "none"),
            column,
            flt.get("value"),
        )

    @property
    def is_attribute(self) -> bool:
        """Attribute tables (filtered fan-out) enrich their target instead of being facts."""
        return self.filter_column is not None


@dataclass
class ViewSpec:
    """Everything needed to (re)write one view and to check it."""

    name: str
    fact: str
    joins: list[ApprovedJoin] = field(default_factory=list)
    derived: list[str] = field(default_factory=list)
    sql: str = ""


def fact_tables(joins: list[ApprovedJoin]) -> list[str]:
    """Tables approved joins start from that no approved join points to."""
    sources = {j.from_table for j in joins if not j.is_attribute}
    targets = {j.to_table for j in joins}
    facts = sorted(sources - targets)
    return facts or sorted(sources)[:1]


def reachable(fact: str, joins: list[ApprovedJoin]) -> list[ApprovedJoin]:
    """Joins to follow from a fact, breadth first, visiting each table once."""
    plain = [j for j in joins if not j.is_attribute]
    attributes = [j for j in joins if j.is_attribute]
    visited, queue, chosen = {fact}, [fact], []
    while queue:
        table = queue.pop(0)
        for join in sorted(plain, key=lambda j: j.edge_id):
            if join.from_table == table and join.to_table not in visited:
                visited.add(join.to_table)
                queue.append(join.to_table)
                chosen.append(join)
    chosen += [a for a in attributes if a.to_table in visited and a.from_table not in visited]
    return chosen


def is_text_date(column: ColumnProfile) -> bool:
    """A YYYYMMDD date stored as text (an ERP habit the views correct)."""
    low, high = column.min_value or "", column.max_value or ""
    return (
        column.type == "VARCHAR"
        and column.fixed_length == 8
        and column.digits_only
        and "19000101" <= low <= high <= "21001231"
    )


def find_column(
    columns: list[ColumnProfile], hints: tuple[str, ...], words: tuple[str, ...]
) -> str | None:
    """A column whose SAP-style hint or name contains all the given words."""
    for column in columns:
        text = f"{FIELD_HINTS.get(column.name.upper(), '')} {column.name}".lower()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        if all(w in text for w in words) or column.name.upper() in hints:
            return column.name
    return None


def wants_aging(requirement: str) -> bool:
    """True when the requirement talks about receivables aging."""
    text = requirement.lower()
    return any(word in text for word in AGING_WORDS)


def aging_columns(
    alias: str, columns: list[ColumnProfile], reference: date, edges: list[int]
) -> list[str]:
    """Due date, days overdue and aging bucket, when a baseline date and payment days exist."""
    baseline = find_column(columns, ("ZFBDT",), ("baseline",))
    days = find_column(columns, ("ZBD1T",), ("payment", "days"))
    if not baseline or not days:
        return []
    due = f"CAST({alias}.{ident(baseline)} + {alias}.{ident(days)} * INTERVAL 1 DAY AS DATE)"
    overdue = f"date_diff('day', {due}, DATE '{reference.isoformat()}')"
    labels = bucket_labels(edges)
    cases = " ".join(
        f"WHEN {overdue} <= {upper} THEN '{label}'"
        for upper, label in zip([0, *edges], labels[:-1], strict=True)
    )
    return [
        f"{due} AS {ident('due_date')}",
        f"{overdue} AS {ident('days_overdue')}",
        f"CASE WHEN {due} IS NULL THEN NULL {cases} ELSE '{labels[-1]}' END "
        f"AS {ident('aging_bucket')}",
    ]


def bucket_labels(edges: list[int]) -> list[str]:
    """`not_due`, `1-30`, `31-60`, ... and the open-ended last bucket, from bucket edges."""
    labels, low = ["not_due"], 1
    for upper in edges:
        labels.append(f"{low}-{upper}")
        low = upper + 1
    return [*labels, f"{edges[-1]}+"]


class View(BaseModel):
    """A generated view as stored and shown: its SQL, status and lineage."""

    name: str
    sql: str
    dialect: str = "duckdb"
    status: Literal["created", "repaired", "failed"]
    fact_table: str
    joins: list[str] = Field(default_factory=list)
    derived_columns: list[str] = Field(default_factory=list)
    message: str | None = None


def literal(value: str) -> str:
    """A safely quoted SQL string literal."""
    return exp.Literal.string(value).sql(dialect="duckdb")


def join_condition(join: ApprovedJoin, from_alias: str, to_alias: str) -> str:
    """The ON clause, applying the recorded normalization (and the filter, for attributes)."""
    left = normalized_sql(f"{from_alias}.{ident(join.from_column)}", join.normalization, "from")
    right = normalized_sql(f"{to_alias}.{ident(join.to_column)}", join.normalization, "to")
    condition = f"{left} = {right}"
    if join.filter_column and join.filter_value is not None:
        condition += f" AND {from_alias}.{ident(join.filter_column)} = {literal(join.filter_value)}"
    return condition


def build_view(
    fact: str,
    joins: list[ApprovedJoin],
    columns: dict[str, list[ColumnProfile]],
    requirement: str,
    settings: KPISettings,
) -> ViewSpec:
    """One view: the fact, left-joined along the chosen joins, plus derived columns."""
    chosen = reachable(fact, joins)
    aliases = {fact: "t0"}
    select = [f"t0.{ident(c.name)} AS {ident(c.name)}" for c in columns[fact]]
    sources = [f"{ident(fact)} AS t0"]
    tables = [(fact, "t0", "")]
    for i, join in enumerate(chosen, start=1):
        alias = f"t{i}"
        if join.is_attribute:
            table, condition = join.from_table, join_condition(join, alias, aliases[join.to_table])
        else:
            table, condition = join.to_table, join_condition(join, aliases[join.from_table], alias)
        aliases[table] = alias
        sources.append(f"LEFT JOIN {ident(table)} AS {alias} ON {condition}")
        select += [
            f"{alias}.{ident(c.name)} AS {ident(f'{table}__{c.name}')}" for c in columns[table]
        ]
        tables.append((table, alias, f"{table}__"))
    derived = []
    for table, alias, prefix in tables:
        for column in columns[table]:
            if is_text_date(column):
                name = f"{prefix}{column.name}_date"
                parsed = f"try_strptime({alias}.{ident(column.name)}, '%Y%m%d')"
                select.append(f"CAST({parsed} AS DATE) AS {ident(name)}")
                derived.append(name)
    if wants_aging(requirement):
        reference = settings.reference_date or date.today()
        aging = aging_columns("t0", columns[fact], reference, settings.aging_bucket_edges)
        select += aging
        derived += ["due_date", "days_overdue", "aging_bucket"] if aging else []
    name = f"v_{fact.lower()}"
    sql = (
        f"CREATE OR REPLACE VIEW {SANDBOX_SCHEMA}.{ident(name)} AS SELECT {', '.join(select)} "
        f"FROM {' '.join(sources)}"
    )
    return ViewSpec(name=name, fact=fact, joins=chosen, derived=derived, sql=sql)


def plan_views(
    proposals: list[dict[str, Any]],
    profile: ProjectProfile,
    requirement: str,
    settings: KPISettings,
) -> list[ViewSpec]:
    """Views for every fact table reachable through the approved proposals."""
    joins = [ApprovedJoin.from_proposal(p) for p in proposals if p.get("status") == "approved"]
    if not joins:
        return []
    columns = {t.name: t.columns for t in profile.tables}
    return [build_view(fact, joins, columns, requirement, settings) for fact in fact_tables(joins)]


def create_views(con: duckdb.DuckDBPyConnection, specs: list[ViewSpec]) -> list[View]:
    """Create each view through the guard; a view that fails is reported, not raised."""
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {SANDBOX_SCHEMA}")
    catalog = catalog_from_connection(con, ("main",))
    views = []
    for spec in specs:
        status: Literal["created", "failed"] = "created"
        message = None
        try:
            spec.sql = guard_sql(spec.sql, catalog, "create_view")
            con.execute(spec.sql)
        except (UnsafeSQLError, duckdb.Error) as error:
            status = "failed"
            message = error.message if isinstance(error, UnsafeSQLError) else type(error).__name__
        views.append(
            View(
                name=spec.name,
                sql=spec.sql,
                status=status,
                fact_table=spec.fact,
                joins=[j.edge_id for j in spec.joins],
                derived_columns=spec.derived,
                message=message,
            )
        )
    return views
