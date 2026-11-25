"""Ground truth written by the generator: true joins, KPI values and question answers.

Everything here is computed in plain Python from the generated rows, independently
of any SQL, so the evaluation compares JoinPilot with an independent answer.
Only `eval/` scripts read the files this module writes.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from joinpilot.config import SynthSettings
from joinpilot.synth.dataset import ErpDataset
from joinpilot.synth.facts import AGING_BUCKETS, Facts, aging_bucket, money
from joinpilot.synth.naming import qualified
from joinpilot.synth.questions import gold_questions

TOP_N = 10

# (from table, from column, to table, to column, normalization, fan-out, filter column, value)
TRUE_JOINS = [
    ("order_headers", "customer_id", "customers", "customer_id", "none", False, None, None),
    ("order_items", "order_id", "order_headers", "order_id", "none", False, None, None),
    ("order_items", "product_id", "products", "product_id", "none", False, None, None),
    ("product_texts", "product_id", "products", "product_id", "none", True, "language", "E"),
    ("open_items", "customer_id", "customers", "customer_id", "lpad_zeros:10", False, None, None),
]
DECOYS = [
    ("order_headers", "net_value", "order_items", "net_value", "same name, different meaning"),
    ("order_headers", "order_date", "customers", "created_on", "dates, not keys"),
    ("customers", "created_on", "products", "created_on", "dates, not keys"),
    ("order_items", "item_no", "open_items", "line_no", "small integers overlap by chance"),
    ("order_headers", "currency", "open_items", "currency", "currency codes, not keys"),
]


def gold_joins(dataset: ErpDataset) -> dict[str, Any]:
    """True join edges (many side first) and decoys, in the dataset's naming."""
    p, n = dataset.planted, dataset.naming
    orphans = {
        ("order_items", "product_id"): p.orphan_item_rows,
        ("open_items", "customer_id"): p.orphan_open_item_rows,
    }
    edges = []
    for ft, fc, tt, tc, norm, fan_out, filter_col, filter_value in TRUE_JOINS:
        edges.append(
            {
                "from": qualified(ft, fc, n),
                "to": qualified(tt, tc, n),
                "cardinality": "N:1",
                "normalization": norm,
                "fan_out": fan_out,
                "filter": (
                    {"column": qualified(ft, filter_col, n), "value": filter_value}
                    if filter_col
                    else None
                ),
                "orphan_rows": orphans.get((ft, fc), 0),
                "null_rows": p.null_key_open_item_rows if ft == "open_items" else 0,
            }
        )
    decoys = [
        {"a": qualified(at, ac, n), "b": qualified(bt, bc, n), "reason": reason}
        for at, ac, bt, bc, reason in DECOYS
    ]
    return {
        "dataset_id": dataset.dataset_id,
        "edges": edges,
        "decoys": decoys,
        "duplicate_customers": [list(pair) for pair in p.duplicate_customers],
    }


def gold_kpis(facts: Facts) -> dict[str, Any]:
    """KPI values as of the reference date (docs/data-model.md)."""
    names = {c["customer_id"]: c["customer_name"] for c in facts.customers}
    buckets: dict[str, Decimal] = dict.fromkeys(AGING_BUCKETS, Decimal(0))
    per_customer: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: dict.fromkeys(AGING_BUCKETS, Decimal(0))
    )
    for row in facts.open_items:
        label = aging_bucket(facts.days_overdue(row))
        buckets[label] += row["amount"]
        customer = facts.master_customer(row["customer_id"])
        if customer:
            per_customer[customer][label] += row["amount"]
    top_open = sorted(per_customer.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))[:TOP_N]

    year = facts.order_year()
    revenue_by_group: dict[str | None, Decimal] = defaultdict(Decimal)
    for item in facts.items:
        if year[item["order_id"]] == 2026:
            product = facts.products.get(item["product_id"])
            revenue_by_group[product["product_group"] if product else None] += item["net_value"]

    revenue_by_customer: dict[str, Decimal] = defaultdict(Decimal)
    for h in facts.headers:
        revenue_by_customer[h["customer_id"]] += h["net_value"]
    top_revenue = sorted(revenue_by_customer.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_N]
    monthly = Counter(f"{h['order_date'][:4]}-{h['order_date'][4:6]}" for h in facts.headers)

    return {
        "reference_date": facts.reference_date.isoformat(),
        "aging_buckets": [{"bucket": b, "amount": money(buckets[b])} for b in AGING_BUCKETS],
        "aging_top_customers": [
            {
                "customer_id": cid,
                "customer_name": names[cid],
                "total": money(sum(b.values(), Decimal(0))),
                **{f"bucket_{label}": money(b[label]) for label in AGING_BUCKETS},
            }
            for cid, b in top_open
        ],
        "revenue_2026_by_product_group": [
            {"product_group": g, "revenue": money(v)}
            for g, v in sorted(revenue_by_group.items(), key=lambda kv: (kv[0] is None, kv[0]))
        ],
        "monthly_order_counts": [{"month": m, "orders": c} for m, c in sorted(monthly.items())],
        "top_customers_by_revenue": [
            {"customer_id": cid, "customer_name": names[cid], "revenue": money(v)}
            for cid, v in top_revenue
        ],
    }


def write_gold(dataset: ErpDataset, out_dir: Path, settings: SynthSettings) -> None:
    """Write joins.json, kpis.json and qa.jsonl for one dataset."""
    facts = Facts.from_dataset(dataset, settings)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "joins.json").write_text(
        json.dumps(gold_joins(dataset), indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "kpis.json").write_text(
        json.dumps(gold_kpis(facts), indent=2) + "\n", encoding="utf-8"
    )
    lines = [json.dumps(q, ensure_ascii=False) for q in gold_questions(dataset.seed, facts)]
    (out_dir / "qa.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
