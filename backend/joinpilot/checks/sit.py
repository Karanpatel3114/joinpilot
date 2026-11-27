"""System integration tests (SIT) for generated views, run automatically after approval.

Each check compares the view with its source tables, the way an analyst would test
a model by hand: are fact rows kept exactly once, do measures still add up, how many
keys find no match or are empty, and does every row land in an aging bucket.
"""

from __future__ import annotations

from typing import Any, Literal

import duckdb
from pydantic import BaseModel

from joinpilot.config import CheckSettings
from joinpilot.profiling.models import ProjectProfile
from joinpilot.profiling.normalize import normalized_sql
from joinpilot.profiling.sql import ident
from joinpilot.sqlgen.guard import SANDBOX_SCHEMA, Catalog, catalog_from_connection, guard_sql
from joinpilot.sqlgen.views import ApprovedJoin, ViewSpec, bucket_labels, literal, types_differ

CheckKind = Literal[
    "row_count", "fan_out", "orphan_keys", "null_keys", "bucket_coverage", "reconciliation"
]
MEASURE_TYPES = ("DECIMAL", "DOUBLE", "FLOAT", "REAL", "HUGEINT")


class CheckResult(BaseModel):
    """One check on one view, with what was observed and what was expected."""

    check_id: str
    view: str
    kind: CheckKind
    passed: bool
    observed: float | int | str | None
    expected: float | int | str | None
    message: str


def scalar(con: duckdb.DuckDBPyConnection, sql: str, catalog: Catalog) -> Any:
    """Run one guarded SELECT and return its single value."""
    row = con.execute(guard_sql(sql, catalog)).fetchone()
    return row[0] if row else None


def ratio(part: int, whole: int) -> float:
    """A share in [0, 1], zero when there is nothing to divide."""
    return round(part / whole, 6) if whole else 0.0


def number(value: Any) -> float | int | None:
    """JSON-friendly numbers for observed and expected values (decimals become floats)."""
    if value is None or isinstance(value, int):
        return value
    return round(float(value), 4)


class ViewChecker:
    """Runs every check for one view against its source tables."""

    def __init__(
        self,
        con: duckdb.DuckDBPyConnection,
        profile: ProjectProfile,
        settings: CheckSettings,
        aging_edges: list[int],
    ) -> None:
        self.con = con
        self.settings = settings
        self.aging_edges = aging_edges
        self.columns = {t.name: t.columns for t in profile.tables}
        self.keys = {t.name: t.candidate_keys for t in profile.tables}
        self.catalog = catalog_from_connection(con, ("main", SANDBOX_SCHEMA))

    def value(self, sql: str) -> Any:
        """Run one guarded SELECT and return its single value."""
        return scalar(self.con, sql, self.catalog)

    def run(self, spec: ViewSpec) -> list[CheckResult]:
        """All checks for one view."""
        view = f"{SANDBOX_SCHEMA}.{ident(spec.name)}"
        results = [self.row_count(spec, view), *self.fan_out(spec, view)]
        for join in spec.joins:
            if not join.is_attribute:
                results += self.key_checks(spec, join)
        results += self.bucket_coverage(spec, view)
        results += self.reconciliation(spec, view)
        return results

    def result(
        self,
        spec: ViewSpec,
        kind: CheckKind,
        detail: str,
        passed: bool,
        observed: Any,
        expected: Any,
        message: str,
    ) -> CheckResult:
        """Build one result with a stable id."""
        check_id = f"{spec.name}:{kind}" + (f":{detail}" if detail else "")
        return CheckResult(
            check_id=check_id,
            view=spec.name,
            kind=kind,
            passed=passed,
            observed=number(observed),
            expected=number(expected),
            message=message,
        )

    def row_count(self, spec: ViewSpec, view: str) -> CheckResult:
        """The view has exactly one row per fact row."""
        rows = int(self.value(f"SELECT COUNT(*) FROM {view}"))
        facts = int(self.value(f"SELECT COUNT(*) FROM {ident(spec.fact)}"))
        message = (
            f"The view keeps all {facts} {spec.fact} rows."
            if rows == facts
            else f"The view has {rows} rows but {spec.fact} has {facts}; a join adds or drops rows."
        )
        return self.result(spec, "row_count", "", rows == facts, rows, facts, message)

    def fan_out(self, spec: ViewSpec, view: str) -> list[CheckResult]:
        """No fact key appears more than once in the view."""
        keys = self.keys.get(spec.fact) or []
        if not keys:
            return []
        columns = ", ".join(ident(c) for c in keys[0])
        duplicated = int(
            self.value(
                f"SELECT COUNT(*) FROM (SELECT {columns} FROM {view} "
                f"GROUP BY {columns} HAVING COUNT(*) > 1)"
            )
        )
        message = (
            "Every fact key appears once."
            if not duplicated
            else f"{duplicated} fact keys appear more than once: a join multiplies rows."
        )
        return [
            self.result(spec, "fan_out", "+".join(keys[0]), duplicated == 0, duplicated, 0, message)
        ]

    def key_checks(self, spec: ViewSpec, join: ApprovedJoin) -> list[CheckResult]:
        """Orphan and null shares of one join's key, within configured limits."""
        source, target = ident(join.from_table), ident(join.to_table)
        key = f"s.{ident(join.from_column)}"
        as_text = types_differ(join, self.columns)
        left = normalized_sql(key, join.normalization, "from", as_text)
        right = normalized_sql(f"t.{ident(join.to_column)}", join.normalization, "to", as_text)
        total = int(self.value(f"SELECT COUNT(*) FROM {source} s"))
        nulls = int(self.value(f"SELECT COUNT(*) FROM {source} s WHERE {key} IS NULL"))
        orphans = int(
            self.value(
                f"SELECT COUNT(*) FROM {source} s LEFT JOIN {target} t ON {left} = {right} "
                f"WHERE {key} IS NOT NULL AND t.{ident(join.to_column)} IS NULL"
            )
        )
        source_ref = f"{join.from_table}.{join.from_column}"
        detail = f"{join.edge_id}:{source_ref}->{join.to_table}.{join.to_column}"
        orphan_rate, null_rate = ratio(orphans, total), ratio(nulls, total)
        return [
            self.result(
                spec,
                "orphan_keys",
                detail,
                orphan_rate <= self.settings.max_orphan_rate,
                orphans,
                round(self.settings.max_orphan_rate * total),
                f"{orphans} {source_ref} values ({orphan_rate:.2%}) have no match in "
                f"{join.to_table}.{join.to_column}.",
            ),
            self.result(
                spec,
                "null_keys",
                detail,
                null_rate <= self.settings.max_null_rate,
                nulls,
                round(self.settings.max_null_rate * total),
                f"{nulls} {source_ref} values ({null_rate:.2%}) are empty.",
            ),
        ]

    def bucket_coverage(self, spec: ViewSpec, view: str) -> list[CheckResult]:
        """Every open item lands in exactly one known aging bucket.

        Items without a due date (an unreadable baseline date or empty payment days) get
        no bucket, so they count as missing: they would drop out of the aging totals.
        """
        if "aging_bucket" not in spec.derived:
            return []
        labels = ", ".join(literal(label) for label in bucket_labels(self.aging_edges))
        missing = int(
            self.value(
                f"SELECT COUNT(*) FROM {view} "
                f"WHERE aging_bucket IS NULL OR aging_bucket NOT IN ({labels})"
            )
        )
        no_due_date = int(self.value(f"SELECT COUNT(*) FROM {view} WHERE due_date IS NULL"))
        message = (
            "Every open item is in an aging bucket."
            if not missing
            else f"{missing} open items have no valid aging bucket "
            f"({no_due_date} of them have no due date)."
        )
        return [self.result(spec, "bucket_coverage", "", missing == 0, missing, 0, message)]

    def reconciliation(self, spec: ViewSpec, view: str) -> list[CheckResult]:
        """Every money column sums to the same total in the view as in the fact table."""
        results = []
        for column in self.columns.get(spec.fact, []):
            if not column.type.startswith(MEASURE_TYPES):
                continue
            name = ident(column.name)
            in_view = self.value(f"SELECT SUM({name}) FROM {view}")
            in_fact = self.value(f"SELECT SUM({name}) FROM {ident(spec.fact)}")
            difference = abs(float(in_view or 0) - float(in_fact or 0))
            allowed = self.settings.reconciliation_tolerance * max(abs(float(in_fact or 0)), 1.0)
            passed = difference <= allowed
            message = (
                f"{column.name} totals agree ({number(in_fact)})."
                if passed
                else f"{column.name} totals differ: {number(in_view)} in the view, "
                f"{number(in_fact)} in {spec.fact}; rows are duplicated or lost."
            )
            results.append(
                self.result(spec, "reconciliation", column.name, passed, in_view, in_fact, message)
            )
        return results


def not_created(view: str, reason: str | None) -> CheckResult:
    """A failing check for a view that could not be built, so the run never looks green."""
    return CheckResult(
        check_id=f"{view}:row_count",
        view=view,
        kind="row_count",
        passed=False,
        observed=None,
        expected="view created",
        message=f"The view could not be created ({reason or 'unknown error'}), so nothing "
        "in it was checked.",
    )


def run_checks(
    con: duckdb.DuckDBPyConnection,
    specs: list[ViewSpec],
    profile: ProjectProfile,
    settings: CheckSettings,
    aging_edges: list[int] | None = None,
) -> list[CheckResult]:
    """Run every check on every view; each statement passes the guard first."""
    checker = ViewChecker(con, profile, settings, aging_edges or [30, 60, 90])
    return [result for spec in specs for result in checker.run(spec)]
