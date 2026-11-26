from collections.abc import Iterator
from datetime import date
from typing import Any

import duckdb
import pytest

from joinpilot.agent.ranking import to_proposal
from joinpilot.config import (
    AgentSettings,
    JoinSettings,
    KPISettings,
    ProfilingSettings,
    SynthSettings,
)
from joinpilot.joins.scoring import score_candidates
from joinpilot.kpi.metrics import MetricDef, define_metrics
from joinpilot.profiling.loader import load_arrow
from joinpilot.profiling.models import ProjectProfile
from joinpilot.profiling.service import profile_project
from joinpilot.sqlgen.guard import SANDBOX_SCHEMA, catalog_from_connection, guard_sql
from joinpilot.sqlgen.views import ViewSpec, create_views, plan_views
from joinpilot.synth.dataset import build_dataset

EVERYTHING = (
    "Open receivables by customer and aging bucket, 2026 revenue by product group, "
    "orders per month and top customers by revenue"
)
KPI = KPISettings(reference_date=date(2026, 6, 30))
ALL_IDS = {
    "aging_buckets",
    "aging_top_customers",
    "revenue_2026_by_product_group",
    "monthly_order_counts",
    "top_customers_by_revenue",
}
Model = tuple[duckdb.DuckDBPyConnection, ProjectProfile, list[ViewSpec]]


def build(naming: str, requirement: str = EVERYTHING) -> Model:
    con = duckdb.connect()
    tables = build_dataset(1, "S", naming, SynthSettings()).output_tables()  # type: ignore[arg-type]
    for name, data in tables.items():
        load_arrow(con, name, data)
    profile = profile_project(con, {n: n for n in tables}, ProfilingSettings())
    proposals = [
        {**to_proposal(c, None, AgentSettings()).model_dump(by_alias=True), "status": "approved"}
        for c in score_candidates(profile, JoinSettings())
        if c.accepted
    ]
    specs = plan_views(proposals, profile, requirement, KPI)
    create_views(con, specs)
    return con, profile, specs


@pytest.fixture(scope="module")
def sap() -> Iterator[Model]:
    model = build("sap")
    yield model
    model[0].close()


def rows(con: duckdb.DuckDBPyConnection, metric: MetricDef) -> list[tuple[Any, ...]]:
    return con.execute(
        guard_sql(metric.sql, catalog_from_connection(con, (SANDBOX_SCHEMA,)))
    ).fetchall()


def by_id(metrics: list[MetricDef]) -> dict[str, MetricDef]:
    return {m.metric_id: m for m in metrics}


def scalar(con: duckdb.DuckDBPyConnection, sql: str) -> Any:
    row = con.execute(sql).fetchone()
    return row[0] if row else None


def test_every_template_applies_to_the_erp_model_and_passes_the_guard(sap: Model) -> None:
    con, profile, specs = sap
    metrics = define_metrics(specs, profile, EVERYTHING, KPI)
    assert {m.metric_id for m in metrics} == ALL_IDS
    assert all(m.requested for m in metrics)
    for metric in metrics:
        assert rows(con, metric), metric.metric_id


def test_aging_buckets_add_up_to_every_open_item(sap: Model) -> None:
    con, profile, specs = sap
    metric = by_id(define_metrics(specs, profile, EVERYTHING, KPI))["aging_buckets"]
    result = rows(con, metric)
    assert [r[0] for r in result] == ["not_due", "1-30", "31-60", "61-90", "90+"]
    assert sum(r[1] for r in result) == scalar(con, "SELECT SUM(DMBTR) FROM BSID")


def test_top_customers_by_aging_match_the_buckets(sap: Model) -> None:
    con, profile, specs = sap
    metric = by_id(define_metrics(specs, profile, EVERYTHING, KPI))["aging_top_customers"]
    result = rows(con, metric)
    assert len(result) == KPI.top_n
    assert all(r[2] == sum(r[3:]) for r in result)
    assert [r[2] for r in result] == sorted((r[2] for r in result), reverse=True)


def test_header_revenue_counts_each_order_once(sap: Model) -> None:
    con, profile, specs = sap
    metric = by_id(define_metrics(specs, profile, EVERYTHING, KPI))["top_customers_by_revenue"]
    direct = con.execute(
        "SELECT KUNNR, SUM(NETWR) AS r FROM VBAK GROUP BY 1 ORDER BY r DESC, KUNNR LIMIT 10"
    ).fetchall()
    assert [(r[0], r[2]) for r in rows(con, metric)] == [(k, round(v, 2)) for k, v in direct]


def test_monthly_orders_and_yearly_revenue_match_the_raw_tables(sap: Model) -> None:
    con, profile, specs = sap
    metrics = by_id(define_metrics(specs, profile, EVERYTHING, KPI))
    monthly = rows(con, metrics["monthly_order_counts"])
    assert sum(r[1] for r in monthly) == scalar(con, "SELECT COUNT(*) FROM VBAK")
    revenue = rows(con, metrics["revenue_2026_by_product_group"])
    assert revenue[-1][0] is None, "items without a known product form the last group"
    assert sum(r[1] for r in revenue) == scalar(
        con,
        "SELECT SUM(i.NETWR) FROM VBAP i JOIN VBAK h ON i.VBELN = h.VBELN "
        "WHERE h.ERDAT LIKE '2026%'",
    )


def test_the_requirement_decides_what_comes_first(sap: Model) -> None:
    _, profile, specs = sap
    metrics = define_metrics(specs, profile, "Open receivables by aging bucket", KPI)
    assert [m.requested for m in metrics] == sorted((m.requested for m in metrics), reverse=True)
    assert {m.metric_id for m in metrics if m.requested} == {"aging_buckets", "aging_top_customers"}
    assert "revenue_by_product_group" in by_id(metrics), "no year asked, so no year filter"


def test_readable_names_give_the_same_metrics() -> None:
    con, profile, specs = build("friendly")
    try:
        metrics = define_metrics(specs, profile, EVERYTHING, KPI)
        assert {m.metric_id for m in metrics} == ALL_IDS
        for metric in metrics:
            assert rows(con, metric), metric.metric_id
    finally:
        con.close()


def test_no_aging_metrics_without_an_aging_view(sap: Model) -> None:
    _, profile, _ = sap
    assert define_metrics([], profile, "Revenue by product group", KPI) == []
    plain = plan_views(
        [
            {
                "edge_id": "e",
                "from": "BSID.KUNNR",
                "to": "KNA1.KUNNR",
                "status": "approved",
                "normalization": "lpad_zeros:10",
            }
        ],
        profile,
        "Revenue by product group",
        KPI,
    )
    assert "aging_bucket" not in plain[0].derived
    assert [m.metric_id for m in define_metrics(plain, profile, "x", KPI)] == []


def profile_of(sql: str) -> list[Any]:
    con = duckdb.connect()
    con.execute(f"CREATE TABLE t AS {sql}")
    return profile_project(con, {"t": "t"}, ProfilingSettings()).tables[0].columns


def test_money_is_never_a_quantity_and_never_a_guess() -> None:
    from joinpilot.kpi.metrics import money

    picked = money(profile_of("SELECT 2.5::DECIMAL(9,2) AS qty, 10.0::DECIMAL(9,2) AS line_total"))
    assert picked is not None and picked.name == "line_total"
    local = money(
        profile_of("SELECT 1.0::DECIMAL(9,2) AS amount_doc, 1.0::DECIMAL(9,2) AS amount_local")
    )
    assert local is not None and local.name == "amount_local"
    assert (
        money(
            profile_of("SELECT 1.0::DECIMAL(9,2) AS gross_amount, 1.0::DECIMAL(9,2) AS tax_amount")
        )
        is None
    )
    assert money(profile_of("SELECT 1.0::DECIMAL(9,2) AS weight")) is None


def test_order_revenue_uses_the_customer_the_approved_join_names() -> None:
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE orders AS SELECT 'O' || i AS order_id, 'C' || (i % 5) AS customer_id, "
        "'C' || ((i + 1) % 5) AS payer_customer_id, 10.0::DECIMAL(9,2) AS net_value, "
        "DATE '2026-01-01' AS order_date FROM range(50) t(i)"
    )
    con.execute(
        "CREATE TABLE items AS SELECT 'O' || (i % 50) AS order_id, i AS item_no, "
        "5.0::DECIMAL(9,2) AS net_value FROM range(100) t(i)"
    )
    con.execute(
        "CREATE TABLE customers AS SELECT 'C' || i AS customer_id, 'Name ' || i AS customer_name "
        "FROM range(5) t(i)"
    )
    profile = profile_project(
        con, {n: n for n in ("orders", "items", "customers")}, ProfilingSettings()
    )
    proposals = [
        {"edge_id": "e1", "from": "items.order_id", "to": "orders.order_id", "status": "approved"},
        {
            "edge_id": "e2",
            "from": "orders.payer_customer_id",
            "to": "customers.customer_id",
            "status": "approved",
        },
    ]
    specs = plan_views(proposals, profile, "top customers by revenue", KPI)
    create_views(con, specs)
    metric = by_id(define_metrics(specs, profile, "top customers by revenue", KPI))[
        "top_customers_by_revenue"
    ]
    assert '"orders__payer_customer_id"' in metric.sql
    result = rows(con, metric)
    assert all(name == f"Name {cid[1:]}" for cid, name, _ in result)
    assert sum(r[2] for r in result) == 500
