from collections.abc import Iterator
from datetime import date
from typing import Any

import duckdb
import pytest

from joinpilot.agent.ranking import to_proposal
from joinpilot.checks.sit import CheckResult, run_checks
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
from joinpilot.sqlgen.views import ApprovedJoin, ViewSpec, build_view, create_views, plan_views
from joinpilot.synth.dataset import build_dataset

AGING = "Open receivables by aging bucket and 2026 revenue by product group"
KPI = KPISettings(reference_date=date(2026, 6, 30))


@pytest.fixture(scope="module")
def warehouse() -> Iterator[tuple[duckdb.DuckDBPyConnection, ProjectProfile]]:
    con = duckdb.connect()
    tables = build_dataset(1, "S", "sap", SynthSettings()).output_tables()
    for name, data in tables.items():
        load_arrow(con, name, data)
    yield con, profile_project(con, {n: n for n in tables}, ProfilingSettings())
    con.close()


def good_views(con: duckdb.DuckDBPyConnection, profile: ProjectProfile) -> list[ViewSpec]:
    proposals = [
        {**to_proposal(c, None, AgentSettings()).model_dump(by_alias=True), "status": "approved"}
        for c in score_candidates(profile, JoinSettings())
        if c.accepted
    ]
    specs = plan_views(proposals, profile, AGING, KPI)
    create_views(con, specs)
    return specs


def find(results: list[CheckResult], view: str, kind: str, source: str) -> CheckResult:
    return next(
        r for r in results if r.view == view and r.kind == kind and f":{source}->" in r.check_id
    )


def by_id(results: list[CheckResult]) -> dict[str, CheckResult]:
    return {r.check_id: r for r in results}


def test_a_correct_model_passes_every_check(warehouse: Any) -> None:
    con, profile = warehouse
    results = run_checks(con, good_views(con, profile), profile, CheckSettings())
    assert results and all(r.passed for r in results), [r.message for r in results if not r.passed]
    kinds = {r.kind for r in results}
    assert kinds == {
        "row_count",
        "fan_out",
        "orphan_keys",
        "null_keys",
        "bucket_coverage",
        "reconciliation",
    }


def test_checks_report_the_planted_orphans_and_null_keys(warehouse: Any) -> None:
    con, profile = warehouse
    results = run_checks(con, good_views(con, profile), profile, CheckSettings())
    items = find(results, "v_vbap", "orphan_keys", "VBAP.MATNR")
    assert items.observed == scalar(
        con,
        "SELECT COUNT(*) FROM VBAP v LEFT JOIN MARA m ON v.MATNR = m.MATNR WHERE m.MATNR IS NULL",
    )
    assert find(results, "v_bsid", "null_keys", "BSID.KUNNR").observed == scalar(
        con, "SELECT COUNT(*) FROM BSID WHERE KUNNR IS NULL"
    )
    strict = run_checks(
        con, good_views(con, profile), profile, CheckSettings(max_orphan_rate=0.001)
    )
    assert not find(strict, "v_vbap", "orphan_keys", "VBAP.MATNR").passed


def scalar(con: duckdb.DuckDBPyConnection, sql: str) -> Any:
    row = con.execute(sql).fetchone()
    return row[0] if row else None


def test_a_join_that_multiplies_rows_fails_three_checks(warehouse: Any) -> None:
    con, profile = warehouse
    columns = {t.name: t.columns for t in profile.tables}
    bad = ApprovedJoin("e9", "VBAP", "MATNR", "MAKT", "MATNR")
    spec = build_view("VBAP", [bad], columns, "revenue", KPI)
    spec.name = "v_bad"
    spec.sql = spec.sql.replace('model."v_vbap"', 'model."v_bad"')
    create_views(con, [spec])
    results = by_id(run_checks(con, [spec], profile, CheckSettings()))
    assert not results["v_bad:row_count"].passed
    assert not results["v_bad:fan_out:VBELN+POSNR"].passed
    assert not results["v_bad:reconciliation:NETWR"].passed
    assert "duplicated" in results["v_bad:reconciliation:NETWR"].message


def test_two_joins_from_one_column_get_distinct_check_ids() -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE f AS SELECT range % 5 AS k FROM range(20)")
    con.execute("CREATE TABLE d1 AS SELECT range AS k FROM range(5)")
    con.execute("CREATE TABLE d2 AS SELECT range AS k FROM range(5)")
    profile = profile_project(con, {"f": "f", "d1": "d1", "d2": "d2"}, ProfilingSettings())
    joins = [ApprovedJoin("e1", "f", "k", "d1", "k"), ApprovedJoin("e2", "f", "k", "d2", "k")]
    spec = build_view("f", joins, {t.name: t.columns for t in profile.tables}, "x", KPI)
    create_views(con, [spec])
    ids = [r.check_id for r in run_checks(con, [spec], profile, CheckSettings())]
    assert len(ids) == len(set(ids))


def test_aging_works_when_the_baseline_date_is_stored_as_text() -> None:
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE BSID AS SELECT range::VARCHAR AS BELNR, "
        "strftime(DATE '2026-05-01' + range * INTERVAL 1 DAY, '%Y%m%d') AS ZFBDT, "
        "30 AS ZBD1T, CAST(10 AS DECIMAL(15,2)) AS DMBTR FROM range(10)"
    )
    profile = profile_project(con, {"b": "BSID"}, ProfilingSettings())
    spec = build_view("BSID", [], {t.name: t.columns for t in profile.tables}, "aging", KPI)
    [view] = create_views(con, [spec])
    assert view.status == "created"
    results = run_checks(con, [spec], profile, CheckSettings())
    assert all(r.passed for r in results if r.kind == "bucket_coverage")


def test_open_items_without_a_due_date_fail_bucket_coverage() -> None:
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE BSID AS SELECT range::VARCHAR AS BELNR, "
        "CASE WHEN range < 3 THEN '20261399' ELSE '20260501' END AS ZFBDT, "
        "30 AS ZBD1T, CAST(10 AS DECIMAL(15,2)) AS DMBTR FROM range(10)"
    )
    profile = profile_project(con, {"b": "BSID"}, ProfilingSettings())
    spec = build_view("BSID", [], {t.name: t.columns for t in profile.tables}, "aging", KPI)
    create_views(con, [spec])
    results = run_checks(con, [spec], profile, CheckSettings())
    [coverage] = [r for r in results if r.kind == "bucket_coverage"]
    assert (coverage.passed, coverage.observed) == (False, 3)
    assert "3 of them have no due date" in coverage.message
