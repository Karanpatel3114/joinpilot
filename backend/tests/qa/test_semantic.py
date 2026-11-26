from datetime import date
from typing import Any

from joinpilot.config import KPISettings
from joinpilot.qa.semantic import describe_columns, model_columns, render_model

KPI = KPISettings(reference_date=date(2026, 6, 30))
Model = Any


def test_every_view_column_gets_a_meaning_and_examples(model: Model) -> None:
    con, profile, specs = model
    facts = {s.name: s.fact for s in specs}
    columns = {
        (c.view, c.name): c for c in describe_columns(model_columns(con), facts, profile, KPI, 2)
    }
    name = columns[("v_bsid", "KNA1__NAME1")]
    assert name.meaning == "name (customer master)" and len(name.examples) == 2
    assert columns[("v_bsid", "DMBTR")].meaning.startswith("amount in local currency")
    assert columns[("v_bsid", "aging_bucket")].examples == [
        "not_due",
        "1-30",
        "31-60",
        "61-90",
        "90+",
    ]
    assert "past the due date" in columns[("v_bsid", "days_overdue")].meaning
    order_date = columns[("v_vbap", "VBAK__ERDAT_date")]
    assert "parsed from YYYYMMDD" in order_date.meaning and order_date.examples == []


def test_the_prompt_text_lists_each_view_once(model: Model) -> None:
    con, profile, specs = model
    facts = {s.name: s.fact for s in specs}
    text = render_model(describe_columns(model_columns(con), facts, profile, KPI, 1))
    assert text.count('model."v_bsid":') == 1 and text.count('model."v_vbap":') == 1
    assert '  "MARA__MATKL" VARCHAR: material product group (material product master).' in text
