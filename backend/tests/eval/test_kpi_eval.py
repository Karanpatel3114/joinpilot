from pathlib import Path

import duckdb
import pytest

from eval.datasets import EvalDataset
from eval.kpi_eval import evaluate_kpis, money_matches, score_rows
from joinpilot.config import ProfilingSettings, Settings, SynthSettings
from joinpilot.profiling.loader import load_arrow
from joinpilot.profiling.service import profile_project
from joinpilot.synth.dataset import build_dataset
from joinpilot.synth.gold import write_gold


@pytest.mark.parametrize("naming", ["sap", "friendly"])
def test_the_dashboard_matches_every_generated_kpi(naming: str, tmp_path: Path) -> None:
    dataset = build_dataset(1, "S", naming, SynthSettings())  # type: ignore[arg-type]
    write_gold(dataset, tmp_path / dataset.dataset_id, SynthSettings())
    con = duckdb.connect()
    tables = dataset.output_tables()
    for name, data in tables.items():
        load_arrow(con, name, data)
    profile = profile_project(con, {n: n for n in tables}, ProfilingSettings())
    evaluated = EvalDataset(dataset.dataset_id, "sha256:x", con, profile, 0.1)
    result = evaluate_kpis([evaluated], Settings(_env_file=None), gold_root=tmp_path)
    per_metric = result["per_dataset"][dataset.dataset_id]
    assert result["aggregate"]["kpi_accuracy"] == 1.0, {
        name: score["wrong"] for name, score in per_metric.items() if score["wrong"]
    }
    assert set(per_metric) == {
        "aging_buckets",
        "aging_top_customers",
        "revenue_2026_by_product_group",
        "monthly_order_counts",
        "top_customers_by_revenue",
    }


def test_money_is_right_within_a_hundredth_of_a_percent() -> None:
    assert money_matches("1000.00", 1000.09)
    assert not money_matches("1000.00", 1000.2)
    assert money_matches("0.00", 0.001) and not money_matches("0.00", 0.01)
    assert not money_matches("5.00", None)


def test_missing_rows_cost_their_values_and_ids_ignore_leading_zeros() -> None:
    gold = [
        {"customer_id": "0000100001", "revenue": "10.00"},
        {"customer_id": "0000100002", "revenue": "5.00"},
    ]
    rows = [{"customer_id": "100001", "revenue": 10.0}]
    score = score_rows("top", gold, rows, ("customer_id", ("revenue",), ()))
    assert (score.right, score.total) == (1, 2)
    assert score.wrong == ["top[100002].revenue"]


def test_an_absent_bucket_counts_as_zero() -> None:
    gold = [{"bucket": "not_due", "amount": "0.00"}, {"bucket": "90+", "amount": "7.50"}]
    rows = [{"bucket": "90+", "amount": 7.5}]
    spec = ("bucket", ("amount",), ())
    assert score_rows("aging", gold, rows, spec, absent_is_zero=True).right == 2
    assert score_rows("aging", gold, rows, spec).right == 1
