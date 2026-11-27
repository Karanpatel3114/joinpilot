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
from dataclasses import asdict, dataclass, field
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
    # "from": the source is an attribute table filtered to one row per key (texts per
    # language); "to": a repair filtered the target to one row per key.
    filter_on: Literal["from", "to"] = "from"

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
        return self.filter_column is not None and self.filter_on == "from"


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
    base_profile = next(c for c in columns if c.name == baseline)
    base = f"{alias}.{ident(baseline)}"
    if is_text_date(base_profile):
        base = f"CAST(try_strptime({base}, '%Y%m%d') AS DATE)"
    due = f"CAST({base} + {alias}.{ident(days)} * INTERVAL 1 DAY AS DATE)"
    overdue = f"date_diff('day', {due}, DATE '{reference.isoformat()}')"
    labels = bucket_labels(edges)
    cases = " ".join(
        f"WHEN {overdue} <= {upper} THEN {literal(label)}"
        for upper, label in zip([0, *edges], labels[:-1], strict=True)
    )
    return [
        f"{due} AS {ident('due_date')}",
        f"{overdue} AS {ident('days_overdue')}",
        f"CASE WHEN {due} IS NULL THEN NULL {cases} ELSE {literal(labels[-1])} END "
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


def types_differ(join: ApprovedJoin, columns: dict[str, list[ColumnProfile]]) -> bool:
    """True when the two key columns have different types, so they must compare as text."""

    def type_of(table: str, name: str) -> str | None:
        return next((c.type for c in columns.get(table, []) if c.name == name), None)

    return type_of(join.from_table, join.from_column) != type_of(join.to_table, join.to_column)


def join_condition(
    join: ApprovedJoin, from_alias: str, to_alias: str, as_text: bool = False
) -> str:
    """The ON clause, applying the recorded normalization (and the filter, for attributes)."""
    left = normalized_sql(
        f"{from_alias}.{ident(join.from_column)}", join.normalization, "from", as_text
    )
    right = normalized_sql(f"{to_alias}.{ident(join.to_column)}", join.normalization, "to", as_text)
    condition = f"{left} = {right}"
    if join.filter_column and join.filter_value is not None:
        alias = from_alias if join.filter_on == "from" else to_alias
        condition += f" AND {alias}.{ident(join.filter_column)} = {literal(join.filter_value)}"
    return condition


def build_view(
    fact: str,
    joins: list[ApprovedJoin],
    columns: dict[str, list[ColumnProfile]],
    requirement: str,
    settings: KPISettings,
) -> ViewSpec:
    """One view: the fact, left-joined along the joins reachable from it, plus derived columns."""
    return render_view(
        ViewSpec(name=f"v_{fact.lower()}", fact=fact, joins=reachable(fact, joins)),
        columns,
        requirement,
        settings,
    )


def render_view(
    spec: ViewSpec, columns: dict[str, list[ColumnProfile]], requirement: str, settings: KPISettings
) -> ViewSpec:
    """Write the SQL for a view whose joins are already chosen (used again by repair)."""
    fact, chosen = spec.fact, spec.joins
    aliases = {fact: "t0"}
    select = [f"t0.{ident(c.name)} AS {ident(c.name)}" for c in columns[fact]]
    sources = [f"{ident(fact)} AS t0"]
    tables = [(fact, "t0", "")]
    for i, join in enumerate(chosen, start=1):
        alias = f"t{i}"
        as_text = types_differ(join, columns)
        if join.is_attribute:
            table = join.from_table
            condition = join_condition(join, alias, aliases[join.to_table], as_text)
        else:
            table = join.to_table
            condition = join_condition(join, aliases[join.from_table], alias, as_text)
        aliases[table] = alias
        sources.append(f"LEFT JOIN {ident(table)} AS {alias} ON {condition}")
        select += [
            f"{alias}.{ident(c.name)} AS {ident(f'{table}__{c.name}')}" for c in columns[table]
        ]
        tables.append((table, alias, f"{table}__"))
    # A derived column never replaces an uploaded column of the same name: DuckDB would
    # rename one of the two, and checks and metrics would read the wrong one.
    taken = {c.name.lower() for c in columns[fact]}
    taken |= {f"{prefix}{c.name}".lower() for t, _, prefix in tables[1:] for c in columns[t]}
    derived = []
    for table, alias, prefix in tables:
        for column in columns[table]:
            name = f"{prefix}{column.name}_date"
            if is_text_date(column) and name.lower() not in taken:
                parsed = f"try_strptime({alias}.{ident(column.name)}, '%Y%m%d')"
                select.append(f"CAST({parsed} AS DATE) AS {ident(name)}")
                derived.append(name)
                taken.add(name.lower())
    aging_names = ["due_date", "days_overdue", "aging_bucket"]
    if wants_aging(requirement) and not taken & set(aging_names):
        reference = settings.reference_date or date.today()
        aging = aging_columns("t0", columns[fact], reference, settings.aging_bucket_edges)
        select += aging
        derived += aging_names if aging else []
    sql = (
        f"CREATE OR REPLACE VIEW {SANDBOX_SCHEMA}.{ident(spec.name)} AS SELECT {', '.join(select)} "
        f"FROM {' '.join(sources)}"
    )
    return ViewSpec(name=spec.name, fact=fact, joins=chosen, derived=derived, sql=sql)


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


def create_views(
    con: duckdb.DuckDBPyConnection,
    specs: list[ViewSpec],
    status: Literal["created", "repaired"] = "created",
) -> list[View]:
    """Create each view through the guard; a view that fails is reported, not raised."""
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {SANDBOX_SCHEMA}")
    catalog = catalog_from_connection(con, ("main",))
    views = []
    for spec in specs:
        outcome: Literal["created", "repaired", "failed"] = status
        message = None
        try:
            spec.sql = guard_sql(spec.sql, catalog, "create_view")
            con.execute(spec.sql)
        except (UnsafeSQLError, duckdb.Error) as error:
            outcome = "failed"
            message = error.message if isinstance(error, UnsafeSQLError) else type(error).__name__
        views.append(
            View(
                name=spec.name,
                sql=spec.sql,
                status=outcome,
                fact_table=spec.fact,
                joins=[j.edge_id for j in spec.joins],
                derived_columns=spec.derived,
                message=message,
            )
        )
    return views


def spec_to_dict(spec: ViewSpec) -> dict[str, Any]:
    """A JSON-friendly form of a view spec, for the run's checkpointed state."""
    return asdict(spec)


def spec_from_dict(data: dict[str, Any]) -> ViewSpec:
    """Rebuild a view spec saved with `spec_to_dict`."""
    joins = [ApprovedJoin(**j) for j in data.get("joins", [])]
    return ViewSpec(
        name=data["name"],
        fact=data["fact"],
        joins=joins,
        derived=list(data.get("derived", [])),
        sql=data.get("sql", ""),
    )
