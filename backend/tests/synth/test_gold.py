import json
from decimal import Decimal
from pathlib import Path

import pytest

from joinpilot.config import SynthSettings
from joinpilot.synth.generate import ErpDataset, build_dataset
from joinpilot.synth.gold import Facts, aging_bucket, gold_joins, gold_kpis, write_gold

SETTINGS = SynthSettings()


@pytest.fixture(scope="module")
def dataset() -> ErpDataset:
    return build_dataset(1, "S", "sap", SETTINGS)


@pytest.mark.parametrize(
    ("days", "bucket"),
    [(-5, "not_due"), (0, "not_due"), (1, "1-30"), (30, "1-30"), (31, "31-60"),
     (60, "31-60"), (61, "61-90"), (90, "61-90"), (91, "90+")],
)  # fmt: skip
def test_aging_bucket_boundaries(days: int, bucket: str) -> None:
    assert aging_bucket(days) == bucket


def test_gold_joins_list_true_edges_with_normalization_and_fan_out(dataset: ErpDataset) -> None:
    joins = gold_joins(dataset)
    edges = {(e["from"], e["to"]): e for e in joins["edges"]}
    assert len(edges) == 5
    assert edges[("BSID.KUNNR", "KNA1.KUNNR")]["normalization"] == "lpad_zeros:10"
    assert edges[("MAKT.MATNR", "MARA.MATNR")]["fan_out"] is True
    assert edges[("VBAP.MATNR", "MARA.MATNR")]["orphan_rows"] == dataset.planted.orphan_item_rows
    assert {d["reason"] for d in joins["decoys"]} >= {"currency codes, not keys"}


def test_friendly_gold_uses_friendly_names() -> None:
    friendly = build_dataset(1, "S", "friendly", SETTINGS)
    froms = {e["from"] for e in gold_joins(friendly)["edges"]}
    assert "open_items.customer_id" in froms


def test_aging_buckets_add_up_to_total_open_amount(dataset: ErpDataset) -> None:
    facts = Facts.from_dataset(dataset, SETTINGS)
    kpis = gold_kpis(facts)
    bucket_total = sum(Decimal(b["amount"]) for b in kpis["aging_buckets"])
    assert bucket_total == sum((r["amount"] for r in facts.open_items), Decimal(0))
    assert len(kpis["aging_top_customers"]) == 10
    assert len(kpis["monthly_order_counts"]) == 18
    assert sum(m["orders"] for m in kpis["monthly_order_counts"]) == 10_000


def test_revenue_by_group_keeps_orphan_items_as_a_null_group(dataset: ErpDataset) -> None:
    kpis = gold_kpis(Facts.from_dataset(dataset, SETTINGS))
    groups = [r["product_group"] for r in kpis["revenue_2026_by_product_group"]]
    assert groups[-1] is None
    assert len(groups) == 11


def test_write_gold_writes_three_files(dataset: ErpDataset, tmp_path: Path) -> None:
    write_gold(dataset, tmp_path, SETTINGS)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["joins.json", "kpis.json", "qa.jsonl"]
    questions = [json.loads(line) for line in (tmp_path / "qa.jsonl").read_text().splitlines()]
    assert len(questions) == 40
    assert len({q["id"] for q in questions}) == 40
    assert all(len(row) == len(q["columns"]) for q in questions for row in q["rows"])
