"""Scoring on small hand-built schemas that differ from the ERP sample."""

import duckdb

from joinpilot.config import JoinSettings, ProfilingSettings
from joinpilot.joins.scoring import score_candidates
from joinpilot.profiling.service import profile_project


def accepted_pairs(*statements: str) -> set[tuple[str, str]]:
    con = duckdb.connect()
    for statement in statements:
        con.execute(statement)
    tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    profile = profile_project(con, {t: t for t in tables}, ProfilingSettings())
    return {(c.from_, c.to) for c in score_candidates(profile, JoinSettings()) if c.accepted}


def test_tables_that_all_use_id_keys_join_through_qualified_names() -> None:
    found = accepted_pairs(
        "CREATE TABLE customers AS SELECT range AS id, 'c' || range AS name FROM range(1, 101)",
        "CREATE TABLE products AS SELECT range AS id, 'p' || range AS name FROM range(1, 51)",
        "CREATE TABLE orders AS SELECT range AS id, (range % 100) + 1 AS customer_id "
        "FROM range(1, 301)",
    )
    assert found == {("orders.customer_id", "customers.id")}


def test_header_item_tables_are_not_flagged_as_fan_out() -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE headers AS SELECT range AS order_id FROM range(100)")
    con.execute(
        "CREATE TABLE items AS SELECT o AS order_id, p AS pos, (o * p) % 7 AS qty "
        "FROM range(100) a(o), range(1, 4) b(p)"
    )
    profile = profile_project(con, {"h": "headers", "i": "items"}, ProfilingSettings())
    [edge] = [c for c in score_candidates(profile, JoinSettings()) if c.accepted]
    assert (edge.from_, edge.to, edge.fan_out_risk) == ("items.order_id", "headers.order_id", False)


def test_equal_scores_prefer_the_better_named_target() -> None:
    found = accepted_pairs(
        "CREATE TABLE customers AS SELECT range AS customer_id FROM range(50)",
        "CREATE TABLE customer_details AS SELECT range AS customer_id FROM range(50)",
        "CREATE TABLE orders AS SELECT range % 50 AS customer_id FROM range(200)",
    )
    targets = {target for source, target in found if source == "orders.customer_id"}
    assert targets == {"customers.customer_id"}
