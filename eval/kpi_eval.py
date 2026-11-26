"""KPI correctness: dashboard metrics against the generator's true KPI values.

The run is the real agent graph with the recommended joins approved, as a person who
trusts the recommendations would get it, and with the gold reference date. Every gold
number is one value to get right (docs/eval-plan.md): counts must match exactly and
money within 0.01% relative error. Rows are matched on their key, customer ids
without leading zeros: a missing row costs the values it should hold, a row gold does
not have costs the values it claims, and two rows with one key are both wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from eval.datasets import EvalDataset
from eval.gold import GOLD_ROOT, load_kpis
from eval.views_eval import rate, run_graph
from joinpilot.config import Settings

MONEY_TOLERANCE = Decimal("0.0001")

# gold key -> (row key column, value columns that are money, value columns that are counts)
SPECS: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "aging_buckets": ("bucket", ("amount",), ()),
    "revenue_2026_by_product_group": ("product_group", ("revenue",), ()),
    "monthly_order_counts": ("month", (), ("orders",)),
    "top_customers_by_revenue": ("customer_id", ("revenue",), ()),
}


def key(column: str, value: Any) -> Any:
    """Row keys compare as text; customer ids without leading zeros."""
    if value is None:
        return None
    text = str(value)
    return (text.lstrip("0") or "0") if column == "customer_id" else text


def money_matches(expected: Any, actual: Any) -> bool:
    """Within 0.01% relative error (or a half cent of zero)."""
    if actual is None:
        return False
    want, got = Decimal(str(expected)), Decimal(str(actual))
    if want == 0:
        return abs(got) < Decimal("0.005")
    return abs(got - want) / abs(want) <= MONEY_TOLERANCE


@dataclass
class Score:
    """Values right out of values expected, per metric."""

    right: int = 0
    total: int = 0
    wrong: list[str] = field(default_factory=list)

    def add(self, ok: bool, what: str) -> None:
        self.total += 1
        self.right += ok
        if not ok and len(self.wrong) < 5:
            self.wrong.append(what)


def score_rows(
    name: str,
    gold: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    spec: tuple[str, tuple[str, ...], tuple[str, ...]],
    absent_is_zero: bool = False,
) -> Score:
    """Compare every gold value with the app row that has the same key.

    App rows whose key gold does not have cost the values they claim, and two app
    rows with one key (after normalising ids) are both treated as wrong.
    """
    column, money, counts = spec
    found: dict[Any, dict[str, Any] | None] = {}
    for row in rows:
        label = key(column, row.get(column))
        found[label] = None if label in found else row
    score = Score()
    gold_keys = set()
    for row in gold:
        label = key(column, row[column])
        gold_keys.add(label)
        mine = found.get(label)
        if label not in found and absent_is_zero:
            mine = dict.fromkeys((*money, *counts), 0)
        for c in money:
            score.add(
                mine is not None and money_matches(row[c], mine.get(c)), f"{name}[{label}].{c}"
            )
        for c in counts:
            score.add(mine is not None and mine.get(c) == row[c], f"{name}[{label}].{c}")
    for label in found.keys() - gold_keys:
        for c in (*money, *counts):
            score.add(False, f"{name}[{label}].{c} (not in gold)")
    return score


def score_kpis(gold: dict[str, Any], metrics: list[dict[str, Any]]) -> dict[str, Score]:
    """Scores for every gold KPI, from the run's computed metrics."""
    computed = {m["metric_id"]: m["data"] for m in metrics if m.get("status") == "computed"}
    scores = {
        name: score_rows(name, gold[name], computed.get(name, []), spec, name == "aging_buckets")
        for name, spec in SPECS.items()
    }
    buckets = [k for k in gold["aging_top_customers"][0] if k.startswith("bucket_")]
    scores["aging_top_customers"] = score_rows(
        "aging_top_customers",
        gold["aging_top_customers"],
        computed.get("aging_top_customers", []),
        ("customer_id", ("total", *buckets), ()),
    )
    return scores


def evaluate_kpis(
    datasets: list[EvalDataset], settings: Settings, gold_root: Path = GOLD_ROOT
) -> dict[str, Any]:
    """KPI accuracy per dataset and metric, and overall, for ERP datasets with gold KPIs."""
    per_dataset: dict[str, Any] = {}
    right = total = 0
    for dataset in datasets:
        gold = load_kpis(dataset.dataset_id, gold_root)
        if gold is None:
            continue
        kpi = settings.kpi.model_copy(
            update={"reference_date": date.fromisoformat(gold["reference_date"])}
        )
        final = run_graph(
            dataset, "approve_all", settings.model_copy(update={"kpi": kpi}), gold_root
        )
        scores = score_kpis(gold, final.get("metrics", []))
        per_dataset[dataset.dataset_id] = {
            name: {
                "accuracy": rate(s.right, s.total),
                "right": s.right,
                "total": s.total,
                "wrong": s.wrong,
            }
            for name, s in scores.items()
        }
        right += sum(s.right for s in scores.values())
        total += sum(s.total for s in scores.values())
    return {
        "aggregate": {"kpi_accuracy": rate(right, total), "right": right, "total": total},
        "per_dataset": per_dataset,
    }
