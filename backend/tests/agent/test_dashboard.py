"""The dashboard step: no numbers from views that lose or duplicate rows."""

from contextlib import nullcontext
from datetime import date
from typing import Any

import duckdb
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from joinpilot.agent import graph as graph_module
from joinpilot.agent.graph import AgentContext, build_graph
from joinpilot.config import KPISettings, ProfilingSettings, Settings
from joinpilot.llm.fake import FakeProvider
from joinpilot.profiling.service import profile_project

REQUIREMENT = "2026 revenue by product group and top customers by revenue"


def run(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    names = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    profile = profile_project(con, {n: n for n in names}, ProfilingSettings())
    settings = Settings(_env_file=None, kpi=KPISettings(reference_date=date(2026, 6, 30)))
    ctx = AgentContext(
        load_profile=lambda: profile,
        llm=FakeProvider(),
        settings=settings,
        warehouse=lambda: nullcontext(con),
    )
    graph = build_graph(ctx, checkpointer=InMemorySaver())
    config: Any = {"configurable": {"thread_id": "t"}}
    paused = graph.invoke({"run_id": "r", "requirement": REQUIREMENT}, config)
    approve = [
        {"edge_id": p["edge_id"], "action": "approve"}
        for p in paused["proposals"]
        if p["recommended"]
    ]
    final: dict[str, Any] = graph.invoke(Command(resume=approve), config)
    return final


def orders_with_a_duplicated_product() -> duckdb.DuckDBPyConnection:
    """2,000 products with one key listed twice: 99.95% unique, so repair leaves it alone."""
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE orders AS SELECT 'O' || lpad(i::VARCHAR, 6, '0') AS order_id, "
        "'C' || lpad((i % 40)::VARCHAR, 4, '0') AS customer_id, "
        "CAST(100 + i AS DECIMAL(12, 2)) AS net_value, "
        "DATE '2026-01-01' + (i % 300)::INT AS created_on FROM range(3000) t(i)"
    )
    con.execute(
        "CREATE TABLE order_items AS SELECT 'O' || lpad((i % 3000)::VARCHAR, 6, '0') AS order_id, "
        "i AS item_no, 'P' || lpad((i % 2000)::VARCHAR, 5, '0') AS product_id, "
        "CAST(10 AS DECIMAL(12, 2)) AS net_value FROM range(9000) t(i)"
    )
    con.execute(
        "CREATE TABLE products AS SELECT 'P' || lpad(i::VARCHAR, 5, '0') AS product_id, "
        "'G' || (i % 4) AS product_group FROM range(2000) t(i) UNION ALL SELECT 'P00001', 'G9'"
    )
    con.execute(
        "CREATE TABLE customers AS SELECT 'C' || lpad(i::VARCHAR, 4, '0') AS customer_id, "
        "'Customer ' || i AS name FROM range(40) t(i)"
    )
    return con


def test_a_view_that_duplicates_rows_gets_no_dashboard_numbers() -> None:
    final = run(orders_with_a_duplicated_product())
    broken = {c["view"] for c in final["checks"] if not c["passed"] and c["kind"] == "fan_out"}
    assert final["status"] == "completed" and broken
    on_broken = [m for m in final["metrics"] if m["view"] in broken]
    assert on_broken, "the order metrics read the broken view"
    for metric in on_broken:
        assert metric["status"] == "failed" and metric["data"] == []
        assert "failed its" in metric["message"] and "fan_out" in metric["message"]
    assert any("was not computed" in w for w in final["warnings"])


def test_a_dashboard_error_does_not_fail_a_finished_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*_: Any) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(graph_module, "define_metrics", explode)
    final = run(orders_with_a_duplicated_product())
    assert final["status"] == "completed" and final["metrics"] == []
    assert "The KPI dashboard could not be built." in final["warnings"]
