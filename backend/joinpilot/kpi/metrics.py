"""Define dashboard metrics from the requirement and the approved data model.

Deterministic, like the views: each metric is a template that applies only when the
model has the columns it needs. Columns are found by meaning, from SAP-style field
hints or readable names, so both naming styles work: money is a DECIMAL column whose
name says value or amount, a customer table is one reached by a join on a customer
key, and so on. Every metric reads one generated view; measures that live on a joined
header table are first reduced to one row per header, so items cannot double them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from joinpilot.config import KPISettings
from joinpilot.glossary.hints import FIELD_HINTS
from joinpilot.profiling.models import ColumnProfile, ProjectProfile
from joinpilot.profiling.sql import ident
from joinpilot.sqlgen.guard import SANDBOX_SCHEMA
from joinpilot.sqlgen.views import ViewSpec, bucket_labels, is_text_date, literal, wants_aging

MONEY_WORDS = ("value", "amount", "revenue", "price")
YEAR = re.compile(r"\b(19|20)\d{2}\b")


class MetricDef(BaseModel):
    """One dashboard metric: what it shows, the SQL that computes it and how to chart it."""

    metric_id: str
    title: str
    description: str
    view: str
    sql: str
    chart: Literal["bar", "line", "table"]
    x: str
    y: list[str]
    requested: bool


def words(column: ColumnProfile) -> str:
    """The column's name and SAP-style hint as lower-case words."""
    text = f"{FIELD_HINTS.get(column.name.upper(), '')} {column.name}".lower()
    return re.sub(r"[^a-z0-9]+", " ", text)


def pick(columns: list[ColumnProfile], *wanted: str) -> ColumnProfile | None:
    """The first column whose words include every wanted word."""
    return next((c for c in columns if all(w in words(c).split() for w in wanted)), None)


def money(columns: list[ColumnProfile]) -> ColumnProfile | None:
    """A money column: DECIMAL, preferring one named like a value or amount."""
    decimals = [c for c in columns if c.type.startswith("DECIMAL")]
    named = [c for c in decimals if any(w in words(c).split() for w in MONEY_WORDS)]
    candidates = named or decimals
    return candidates[0] if candidates else None


def date_column(columns: list[ColumnProfile]) -> ColumnProfile | None:
    """A date column, real or stored as YYYYMMDD text."""
    return next((c for c in columns if c.type == "DATE" or is_text_date(c)), None)


@dataclass(frozen=True)
class ViewModel:
    """A view's columns, grouped by the table they come from."""

    spec: ViewSpec
    columns: dict[str, list[ColumnProfile]]

    def name(self, table: str, column: ColumnProfile, as_date: bool = False) -> str:
        """The view column for a source column (dates use the derived DATE column)."""
        base = column.name if table == self.spec.fact else f"{table}__{column.name}"
        return f"{base}_date" if as_date and is_text_date(column) else base

    def ref(self, table: str, column: ColumnProfile, as_date: bool = False) -> str:
        """A quoted reference to that view column."""
        return ident(self.name(table, column, as_date))

    def table_columns(self, found: tuple[str, ColumnProfile] | None) -> list[ColumnProfile]:
        """The columns of a table found by `joined_on`, or none."""
        return self.columns[found[0]] if found else []

    def joined_on(self, *wanted: str) -> tuple[str, ColumnProfile] | None:
        """A table joined into the view on a key with the wanted words, and that key."""
        for join in self.spec.joins:
            if join.is_attribute:
                continue
            key = next(c for c in self.columns[join.to_table] if c.name == join.to_column)
            if all(w in words(key).split() for w in wanted):
                return join.to_table, key
        return None

    @property
    def source(self) -> str:
        return f"{SANDBOX_SCHEMA}.{ident(self.spec.name)}"


def aging_metrics(model: ViewModel, settings: KPISettings, requested: bool) -> list[MetricDef]:
    """Open amount by aging bucket, overall and for the top customers."""
    if "aging_bucket" not in model.spec.derived:
        return []
    amount = money(model.columns[model.spec.fact])
    if amount is None:
        return []
    value = model.ref(model.spec.fact, amount)
    labels = bucket_labels(settings.aging_bucket_edges)
    order = " ".join(f"WHEN {literal(label)} THEN {i}" for i, label in enumerate(labels))
    bucket = ident("aging_bucket")
    metrics = [
        MetricDef(
            metric_id="aging_buckets",
            title="Open receivables by aging bucket",
            description=f"Sum of {amount.name} per aging bucket, as of the reference date.",
            view=model.spec.name,
            sql=(
                f"SELECT {bucket} AS bucket, ROUND(SUM({value}), 2) AS amount "
                f"FROM {model.source} GROUP BY {bucket} "
                f"ORDER BY CASE {bucket} {order} ELSE {len(labels)} END"
            ),
            chart="bar",
            x="bucket",
            y=["amount"],
            requested=requested,
        )
    ]
    customers = model.joined_on("customer")
    name = pick(model.table_columns(customers), "name")
    if customers and name:
        table, key = customers
        columns = ", ".join(
            f"ROUND(SUM(CASE WHEN {bucket} = {literal(label)} THEN {value} ELSE 0 END), 2) "
            f"AS {ident(f'bucket_{label}')}"
            for label in labels
        )
        metrics.append(
            MetricDef(
                metric_id="aging_top_customers",
                title=f"Top {settings.top_n} customers by open amount",
                description=(
                    f"Open {amount.name} per {table} customer and aging bucket; items without a "
                    "matching customer are left out."
                ),
                view=model.spec.name,
                sql=(
                    f"SELECT {model.ref(table, key)} AS customer_id, "
                    f"MAX({model.ref(table, name)}) AS customer_name, "
                    f"ROUND(SUM({value}), 2) AS total, {columns} FROM {model.source} "
                    f"WHERE {model.ref(table, key)} IS NOT NULL GROUP BY 1 "
                    f"ORDER BY total DESC, customer_id LIMIT {settings.top_n}"
                ),
                chart="bar",
                x="customer_name",
                y=[f"bucket_{label}" for label in labels],
                requested=requested,
            )
        )
    return metrics


def order_metrics(model: ViewModel, requirement: str, settings: KPISettings) -> list[MetricDef]:
    """Revenue by product group, monthly orders and top customers by revenue."""
    header = model.joined_on("order")
    if header is None:
        return []
    table, order_key = header
    order_date = date_column(model.columns[table])
    if order_date is None:
        return []
    text = requirement.lower()
    day = model.ref(table, order_date, as_date=True)
    order = model.ref(table, order_key)
    metrics: list[MetricDef] = []

    item_value = money(model.columns[model.spec.fact])
    products = model.joined_on("product")
    group = pick(model.table_columns(products), "group")
    if item_value and products and group:
        year = YEAR.search(requirement)
        where = f" WHERE year({day}) = {year.group(0)}" if year else ""
        label = f"{year.group(0)} revenue" if year else "Revenue"
        metrics.append(
            MetricDef(
                metric_id=f"revenue_{year.group(0)}_by_product_group"
                if year
                else "revenue_by_product_group",
                title=f"{label} by product group",
                description=(
                    f"Sum of item {item_value.name} by {products[0]}.{group.name}"
                    + (f" for orders dated in {year.group(0)}" if year else "")
                    + "; items without a known product form an empty group."
                ),
                view=model.spec.name,
                sql=(
                    f"SELECT {model.ref(products[0], group)} AS product_group, "
                    f"ROUND(SUM({model.ref(model.spec.fact, item_value)}), 2) AS revenue "
                    f"FROM {model.source}{where} GROUP BY 1 ORDER BY 1 NULLS LAST"
                ),
                chart="bar",
                x="product_group",
                y=["revenue"],
                requested="group" in text or "product" in text,
            )
        )

    metrics.append(
        MetricDef(
            metric_id="monthly_order_counts",
            title="Orders per month",
            description=f"Distinct {table}.{order_key.name} per month of {order_date.name}.",
            view=model.spec.name,
            sql=(
                f"SELECT strftime({day}, '%Y-%m') AS month, COUNT(DISTINCT {order}) AS orders "
                f"FROM {model.source} WHERE {day} IS NOT NULL GROUP BY 1 ORDER BY 1"
            ),
            chart="line",
            x="month",
            y=["orders"],
            requested="month" in text or "orders" in text,
        )
    )

    header_value = money(model.columns[table])
    customer = pick(model.columns[table], "customer")
    master = model.joined_on("customer")
    name = pick(model.table_columns(master), "name")
    if header_value and customer:
        name_sql = f", {model.ref(master[0], name)} AS n" if master and name else ""
        metrics.append(
            MetricDef(
                metric_id="top_customers_by_revenue",
                title=f"Top {settings.top_n} customers by revenue",
                description=(
                    f"Sum of {table}.{header_value.name} per {table}.{customer.name}, counting "
                    "each order once however many items it has."
                ),
                view=model.spec.name,
                sql=(
                    f"SELECT c AS customer_id, {'MAX(n)' if name_sql else 'c'} AS customer_name, "
                    f"ROUND(SUM(v), 2) AS revenue FROM (SELECT DISTINCT {order} AS o, "
                    f"{model.ref(table, customer)} AS c, {model.ref(table, header_value)} AS v"
                    f"{name_sql} FROM {model.source}) AS orders WHERE c IS NOT NULL "
                    f"GROUP BY c ORDER BY revenue DESC, customer_id LIMIT {settings.top_n}"
                ),
                chart="bar",
                x="customer_name",
                y=["revenue"],
                requested="customer" in text and "revenue" in text,
            )
        )
    return metrics


def define_metrics(
    specs: list[ViewSpec], profile: ProjectProfile, requirement: str, settings: KPISettings
) -> list[MetricDef]:
    """Every metric the model supports, the ones the requirement asks for first."""
    columns = {t.name: t.columns for t in profile.tables}
    metrics: list[MetricDef] = []
    for spec in specs:
        model = ViewModel(spec, columns)
        metrics += aging_metrics(model, settings, wants_aging(requirement))
        metrics += order_metrics(model, requirement, settings)
    unique: dict[str, MetricDef] = {}
    for metric in metrics:
        unique.setdefault(metric.metric_id, metric)
    return sorted(unique.values(), key=lambda m: not m.requested)
