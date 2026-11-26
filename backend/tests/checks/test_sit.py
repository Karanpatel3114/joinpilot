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
    results = by_id(run_checks(con, good_views(con, profile), profile, CheckSettings()))
    items = results["v_vbap:orphan_keys:VBAP.MATNR"]
    assert items.observed == scalar(
        con,
        "SELECT COUNT(*) FROM VBAP v LEFT JOIN MARA m ON v.MATNR = m.MATNR WHERE m.MATNR IS NULL",
    )
    assert results["v_bsid:null_keys:BSID.KUNNR"].observed == scalar(
        con, "SELECT COUNT(*) FROM BSID WHERE KUNNR IS NULL"
    )
    strict = by_id(
        run_checks(con, good_views(con, profile), profile, CheckSettings(max_orphan_rate=0.001))
    )
    assert not strict["v_vbap:orphan_keys:VBAP.MATNR"].passed


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
