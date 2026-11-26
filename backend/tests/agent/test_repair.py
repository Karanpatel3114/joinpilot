from datetime import date
from typing import Any

import duckdb
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from joinpilot.agent.graph import AgentContext, build_graph
from joinpilot.agent.repair import repair_spec
from joinpilot.checks.sit import run_checks
from joinpilot.config import CheckSettings, JoinSettings, KPISettings
from joinpilot.profiling.models import ProjectProfile
from joinpilot.sqlgen.views import ApprovedJoin, ViewSpec, create_views, render_view

KPI = KPISettings(reference_date=date(2026, 6, 30))


def columns(profile: ProjectProfile) -> dict[str, Any]:
    return {t.name: t.columns for t in profile.tables}


def test_a_join_to_a_text_table_is_filtered_to_one_language(
    sap_profile: ProjectProfile, sample_warehouse: duckdb.DuckDBPyConnection
) -> None:
    bad = ViewSpec(
        name="v_items_texts",
        fact="VBAP",
        joins=[ApprovedJoin("e9", "VBAP", "MATNR", "MAKT", "MATNR")],
    )
    fixed, notes = repair_spec(bad, sap_profile, JoinSettings())
    [join] = fixed.joins
    assert (join.filter_column, join.filter_value, join.filter_on) == ("SPRAS", "E", "to")
    assert "MAKT.SPRAS = 'E'" in notes[0]
    spec = render_view(fixed, columns(sap_profile), "revenue", KPI)
    [view] = create_views(sample_warehouse, [spec], status="repaired")
    assert view.status == "repaired"
    results = run_checks(sample_warehouse, [spec], sap_profile, CheckSettings())
    assert all(r.passed for r in results if r.kind in ("row_count", "fan_out", "reconciliation"))


def test_joins_with_no_way_to_be_made_unique_are_removed_with_their_branch(
    sap_profile: ProjectProfile,
) -> None:
    spec = ViewSpec(
        name="v",
        fact="VBAK",
        joins=[
            ApprovedJoin("e1", "VBAK", "KUNNR", "BSID", "KUNNR", "strip_leading_zeros"),
            ApprovedJoin("e2", "BSID", "BUKRS", "VBAK", "VKORG"),
        ],
    )
    fixed, notes = repair_spec(spec, sap_profile, JoinSettings())
    assert fixed.joins == []
    assert "was removed" in notes[0]


def test_the_agent_repairs_a_bad_approval_and_checks_pass_afterwards(ctx: AgentContext) -> None:
    graph = build_graph(ctx, checkpointer=InMemorySaver())
    config: Any = {"configurable": {"thread_id": "repair"}}
    state = graph.invoke({"run_id": "r", "requirement": "Revenue by product"}, config)
    decisions = [
        {"edge_id": p["edge_id"], "action": "approve"}
        for p in state["proposals"]
        if p["recommended"] and p["from"] != "MAKT.MATNR"
    ]
    texts = next(
        p for p in state["proposals"] if (p["from"], p["to"]) == ("VBAP.MATNR", "MAKT.MATNR")
    )
    decisions.append({"edge_id": texts["edge_id"], "action": "approve"})
    final = graph.invoke(Command(resume=decisions), config)
    views = {v["name"]: v for v in final["views"]}
    assert views["v_vbap"]["status"] == "repaired"
    assert final["repair_attempts"] == 1
    structural = [
        c for c in final["checks"] if c["kind"] in ("row_count", "fan_out", "reconciliation")
    ]
    assert structural and all(c["passed"] for c in structural)
    assert any("SPRAS = 'E'" in w for w in final["warnings"])
    assert final["status"] == "completed"
