from collections.abc import Iterator
from datetime import date
from typing import Any

import duckdb
import pytest

from joinpilot.agent.ranking import to_proposal
from joinpilot.checks.sit import run_checks
from joinpilot.config import (
    AgentSettings,
    CheckSettings,
    JoinSettings,
    KPISettings,
    ProfilingSettings,
    SynthSettings,
)
from joinpilot.joins.scoring import score_candidates
from joinpilot.profiling.loader import load_arrow
from joinpilot.profiling.models import ProjectProfile
from joinpilot.profiling.service import profile_project
from joinpilot.sqlgen.views import (
    ApprovedJoin,
    bucket_labels,
    build_view,
    create_views,
    fact_tables,
    literal,
    plan_views,
    reachable,
)
from joinpilot.synth.dataset import build_dataset
from joinpilot.synth.naming import Naming

KPI = KPISettings(reference_date=date(2026, 6, 30))
CHECKS = CheckSettings()
AGING = "Open receivables by aging bucket and 2026 revenue by product group"


@pytest.fixture(scope="module", params=["sap", "friendly"])
def warehouse(
    request: pytest.FixtureRequest,
) -> Iterator[tuple[duckdb.DuckDBPyConnection, ProjectProfile, Naming]]:
    con = duckdb.connect()
    tables = build_dataset(1, "S", request.param, SynthSettings()).output_tables()
    for name, data in tables.items():
        load_arrow(con, name, data)
    yield con, profile_project(con, {n: n for n in tables}, ProfilingSettings()), request.param
    con.close()


def approved(profile: ProjectProfile) -> list[dict[str, Any]]:
    return [
        {**to_proposal(c, None, AgentSettings()).model_dump(by_alias=True), "status": "approved"}
        for c in score_candidates(profile, JoinSettings())
        if c.accepted
    ]


def scalar(con: duckdb.DuckDBPyConnection, sql: str) -> Any:
    row = con.execute(sql).fetchone()
    return row[0] if row else None


def test_one_view_per_fact_keeps_every_fact_row_once(warehouse: Any) -> None:
    con, profile, naming = warehouse
    views = create_views(con, plan_views(approved(profile), profile, AGING, KPI))
    items, open_items = ("VBAP", "BSID") if naming == "sap" else ("order_items", "open_items")
    assert {v.name for v in views} == {f"v_{items.lower()}", f"v_{open_items.lower()}"}
    assert all(v.status == "created" for v in views)
    for fact in (items, open_items):
        assert scalar(con, f'SELECT COUNT(*) FROM model."v_{fact.lower()}"') == scalar(
            con, f'SELECT COUNT(*) FROM "{fact}"'
        )


def test_normalized_join_matches_every_customer_that_exists(warehouse: Any) -> None:
    con, profile, naming = warehouse
    create_views(con, plan_views(approved(profile), profile, AGING, KPI))
    fact, master, key = (
        ("BSID", "KNA1", "KUNNR") if naming == "sap" else ("open_items", "customers", "customer_id")
    )
    matched = scalar(con, f'SELECT COUNT("{master}__{key}") FROM model."v_{fact.lower()}"')
    expected = scalar(
        con,
        f'SELECT COUNT(*) FROM "{fact}" f JOIN "{master}" m '
        f'ON lpad(f."{key}", 10, \'0\') = m."{key}"',
    )
    assert matched == expected > 0


def test_aging_buckets_match_a_direct_computation(warehouse: Any) -> None:
    con, profile, naming = warehouse
    create_views(con, plan_views(approved(profile), profile, AGING, KPI))
    fact, base, days, amount = (
        ("BSID", "ZFBDT", "ZBD1T", "DMBTR")
        if naming == "sap"
        else ("open_items", "baseline_date", "payment_days", "amount")
    )
    from_view = dict(
        con.execute(
            f'SELECT aging_bucket, SUM("{amount}") FROM model."v_{fact.lower()}" GROUP BY 1'
        ).fetchall()
    )
    direct = dict(
        con.execute(f"""
        SELECT CASE WHEN d <= 0 THEN 'not_due' WHEN d <= 30 THEN '1-30' WHEN d <= 60 THEN '31-60'
                    WHEN d <= 90 THEN '61-90' ELSE '90+' END, SUM(a)
        FROM (SELECT date_diff('day', CAST("{base}" + "{days}" * INTERVAL 1 DAY AS DATE),
                               DATE '2026-06-30') AS d, "{amount}" AS a FROM "{fact}") GROUP BY 1
    """).fetchall()
    )
    assert from_view == direct


def test_texts_are_attached_with_their_filter_and_text_dates_are_parsed(warehouse: Any) -> None:
    con, profile, naming = warehouse
    create_views(con, plan_views(approved(profile), profile, AGING, KPI))
    if naming != "sap":
        pytest.skip("text dates and SAP-style columns are checked on the sap naming")
    english = scalar(
        con,
        "SELECT COUNT(*) FROM model.v_vbap v JOIN MAKT t "
        "ON t.MATNR = v.MATNR AND t.SPRAS = 'E' AND t.MAKTX = v.MAKT__MAKTX",
    )
    assert english == scalar(con, "SELECT COUNT(MAKT__MAKTX) FROM model.v_vbap") > 0
    assert scalar(con, 'SELECT MIN("VBAK__ERDAT_date") FROM model.v_vbap') == date(2025, 1, 1)


def test_requirements_without_aging_get_no_aging_columns(warehouse: Any) -> None:
    _, profile, _ = warehouse
    specs = plan_views(approved(profile), profile, "Revenue by product group", KPI)
    assert all("aging_bucket" not in s.derived for s in specs)


def test_nothing_is_built_without_approvals(warehouse: Any) -> None:
    _, profile, _ = warehouse
    proposals = [{**p, "status": "rejected"} for p in approved(profile)]
    assert plan_views(proposals, profile, AGING, KPI) == []


def test_facts_and_reachable_joins_follow_the_approved_graph() -> None:
    def join(edge: str, a: str, b: str, filt: str | None = None) -> ApprovedJoin:
        return ApprovedJoin(
            edge, a, "k", b, "k", filter_column=filt, filter_value="E" if filt else None
        )

    joins = [
        join("e1", "items", "orders"),
        join("e2", "orders", "customers"),
        join("e3", "items", "products"),
        join("e4", "texts", "products", "lang"),
        join("e5", "customers", "orders"),
    ]
    assert fact_tables(joins) == ["items"]
    assert [j.edge_id for j in reachable("items", joins)] == ["e1", "e3", "e2", "e4"]


def test_bucket_labels_and_literals_are_safe() -> None:
    assert bucket_labels([30, 60, 90]) == ["not_due", "1-30", "31-60", "61-90", "90+"]
    assert literal("O'Neil") == "'O''Neil'"


def test_a_view_the_guard_refuses_is_reported_not_raised(warehouse: Any) -> None:
    con, profile, _ = warehouse
    specs = plan_views(approved(profile), profile, AGING, KPI)
    specs[0].sql = specs[0].sql.replace("SELECT ", "SELECT read_csv('x') AS bad, ", 1)
    views = create_views(con, specs)
    assert views[0].status == "failed" and views[0].message


def test_keys_of_different_types_join_as_text_like_profiling_compared_them() -> None:
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE items AS SELECT i AS item_id, 1000 + i % 50 AS matnr, "
        "CAST(i AS DECIMAL(12, 2)) AS amount FROM range(200) r(i)"
    )
    con.execute(
        "CREATE TABLE mara AS SELECT CAST(1000 + i AS VARCHAR) AS matnr, 'grp' || i % 3 AS grp "
        "FROM range(50) r(i) UNION ALL SELECT 'MAT-X', 'grp0'"
    )
    profile = profile_project(con, {"items": "items", "mara": "mara"}, ProfilingSettings())
    joins = approved(profile)
    assert joins, "the integer-to-text key should still be proposed"
    views = create_views(con, plan_views(joins, profile, "revenue by group", KPI))
    assert [v.status for v in views] == ["created"]
    assert 'CAST(t0."matnr" AS TEXT)' in views[0].sql
    assert scalar(con, 'SELECT COUNT(mara__grp) FROM model."v_items"') == 200
    results = run_checks(con, plan_views(joins, profile, "revenue by group", KPI), profile, CHECKS)
    assert all(r.passed for r in results if r.kind in ("row_count", "orphan_keys"))
    con.close()


def test_derived_columns_never_shadow_uploaded_columns_of_the_same_name() -> None:
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE BSID AS SELECT range::VARCHAR AS BELNR, '20260501' AS ZFBDT, "
        "'kept' AS ZFBDT_date, 30 AS ZBD1T, 'mine' AS aging_bucket, "
        "CAST(10 AS DECIMAL(15,2)) AS DMBTR FROM range(5)"
    )
    profile = profile_project(con, {"b": "BSID"}, ProfilingSettings())
    spec = build_view("BSID", [], {t.name: t.columns for t in profile.tables}, "aging", KPI)
    assert spec.derived == []
    [view] = create_views(con, [spec])
    assert view.status == "created"
    columns = [r[0] for r in con.execute('DESCRIBE model."v_bsid"').fetchall()]
    assert columns == ["BELNR", "ZFBDT", "ZFBDT_date", "ZBD1T", "aging_bucket", "DMBTR"]
    con.close()
