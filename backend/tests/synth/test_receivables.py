from datetime import timedelta
from typing import Any

import pytest

from joinpilot.config import SynthSettings
from joinpilot.synth.masters import make_customers
from joinpilot.synth.receivables import make_open_items

SETTINGS = SynthSettings()


@pytest.fixture(scope="module")
def rows() -> list[dict[str, Any]]:
    return make_open_items(1, 3_000, make_customers(1, 300), SETTINGS).to_pylist()


def test_generates_exactly_the_requested_number_of_lines(rows: list[dict[str, Any]]) -> None:
    assert len(rows) == 3_000


def test_document_and_line_number_identify_each_row(rows: list[dict[str, Any]]) -> None:
    keys = {(r["document_no"], r["line_no"]) for r in rows}
    assert len(keys) == len(rows)
    assert {r["line_no"] for r in rows} <= {1, 2, 3}


def test_dates_are_consistent_and_before_the_reference_date(
    rows: list[dict[str, Any]],
) -> None:
    for r in rows:
        doc_date, baseline = r["document_date"], r["baseline_date"]
        assert SETTINGS.open_item_start <= doc_date <= SETTINGS.reference_date
        assert timedelta(0) <= baseline - doc_date <= timedelta(days=5)
        assert r["fiscal_year"] == doc_date.year
        assert r["payment_days"] in {0, 14, 30, 45, 60, 90}


def test_aging_spans_not_due_and_long_overdue(rows: list[dict[str, Any]]) -> None:
    overdue_days = [
        (SETTINGS.reference_date - (r["baseline_date"] + timedelta(days=r["payment_days"]))).days
        for r in rows
    ]
    assert any(d <= 0 for d in overdue_days)
    assert any(1 <= d <= 30 for d in overdue_days)
    assert any(d > 90 for d in overdue_days)


def test_customers_come_from_the_master_before_issues_are_planted(
    rows: list[dict[str, Any]],
) -> None:
    master = set(make_customers(1, 300).column("customer_id").to_pylist())
    assert {r["customer_id"] for r in rows} <= master
