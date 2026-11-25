"""Plant realistic data-quality issues into clean tables, and record what was planted.

The record is ground truth: the gold writer uses it, and the evaluation checks
whether JoinPilot finds each issue.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyarrow as pa

from joinpilot.config import IssueRates
from joinpilot.synth.rng import stream


@dataclass(frozen=True)
class PlantedIssues:
    """Exactly which issues were planted, for the gold files."""

    duplicate_customers: list[tuple[str, str]]  # (duplicate id, original id)
    orphan_product_ids: list[str]  # only ids that some row actually uses
    orphan_item_rows: int
    orphan_customer_numbers: list[str]  # in master format, before zeros are stripped
    orphan_open_item_rows: int
    null_key_open_item_rows: int
    stripped_zero_rows: int


def pick_rows(rng: np.random.Generator, n: int, rate: float, exclude: set[int]) -> list[int]:
    """Pick round(rate * n) distinct row positions that are not in `exclude`."""
    candidates = np.array([i for i in range(n) if i not in exclude], dtype=np.int64)
    k = min(round(rate * n), len(candidates))
    return sorted(int(i) for i in rng.choice(candidates, size=k, replace=False))


def unused_ids(rng: np.random.Generator, k: int, existing: set[str], width: int) -> list[str]:
    """Draw `k` ids that look like real ones (same width and range) but do not exist."""
    numbers = [int(x) for x in existing]
    low, high = min(numbers), max(numbers) + 1
    out: list[str] = []
    while len(out) < k:
        candidate = str(int(rng.integers(low, high))).zfill(width)
        if candidate not in existing and candidate not in out:
            out.append(candidate)
    return out


def string_set(table: pa.Table, column: str) -> set[str]:
    """Return the distinct non-null string values of a column."""
    return {str(v) for v in table.column(column).to_pylist() if v is not None}


def replace_column(table: pa.Table, name: str, values: list[str | None]) -> pa.Table:
    """Return `table` with one string column replaced."""
    return table.set_column(table.column_names.index(name), name, pa.array(values, pa.string()))


def plant_duplicate_customers(
    seed: int, customers: pa.Table, rate: float
) -> tuple[pa.Table, list[tuple[str, str]]]:
    """Give a few customers the same name and location as another customer."""
    rng = stream(seed, "issue:duplicate_customers")
    rows = customers.to_pylist()
    dup_rows = pick_rows(rng, len(rows), rate, exclude=set())
    pairs: list[tuple[str, str]] = []
    for i in dup_rows:
        j = int(rng.integers(len(rows)))
        while j in dup_rows:
            j = int(rng.integers(len(rows)))
        for column in ("customer_name", "country_code", "city"):
            rows[i][column] = rows[j][column]
        pairs.append((rows[i]["customer_id"], rows[j]["customer_id"]))
    return pa.Table.from_pylist(rows, schema=customers.schema), pairs


def plant_orphan_products(
    seed: int, items: pa.Table, product_ids: set[str], rate: float
) -> tuple[pa.Table, list[str], int]:
    """Point some order items at products that are missing from the master."""
    rng = stream(seed, "issue:orphan_products")
    values: list[str | None] = items.column("product_id").to_pylist()
    rows = pick_rows(rng, len(values), rate, exclude=set())
    pool = unused_ids(rng, max(1, len(rows) // 3), product_ids, width=18)
    for i in rows:
        values[i] = pool[int(rng.integers(len(pool)))]
    used = sorted({str(values[i]) for i in rows})
    return replace_column(items, "product_id", values), used, len(rows)


def plant_open_item_key_issues(
    seed: int, open_items: pa.Table, customer_ids: set[str], rates: IssueRates
) -> tuple[pa.Table, list[str], int, int, int]:
    """Add orphan and null customer keys, then strip leading zeros from stored keys."""
    rng = stream(seed, "issue:open_item_keys")
    values: list[str | None] = open_items.column("customer_id").to_pylist()
    orphan_rows = pick_rows(rng, len(values), rates.orphan_open_items, exclude=set())
    pool = unused_ids(rng, max(1, len(orphan_rows) // 2), customer_ids, width=10)
    for i in orphan_rows:
        values[i] = pool[int(rng.integers(len(pool)))]
    used = sorted({str(values[i]) for i in orphan_rows})
    null_rows = pick_rows(rng, len(values), rates.null_key_open_items, set(orphan_rows))
    for i in null_rows:
        values[i] = None
    non_null = [i for i, v in enumerate(values) if v is not None]
    strip_rows = [
        non_null[int(k)]
        for k in rng.choice(
            len(non_null), round(rates.stripped_zeros_open_items * len(non_null)), replace=False
        )
    ]
    for i in strip_rows:
        value = values[i]
        if value is not None:
            values[i] = str(int(value))
    table = replace_column(open_items, "customer_id", values)
    return table, used, len(orphan_rows), len(null_rows), len(strip_rows)


def plant_issues(
    seed: int,
    customers: pa.Table,
    products: pa.Table,
    items: pa.Table,
    open_items: pa.Table,
    rates: IssueRates,
) -> tuple[pa.Table, pa.Table, pa.Table, PlantedIssues]:
    """Apply every planted issue and return the changed tables plus the record."""
    customer_ids = string_set(customers, "customer_id")
    customers, pairs = plant_duplicate_customers(seed, customers, rates.duplicate_customers)
    items, orphan_products, orphan_items = plant_orphan_products(
        seed, items, string_set(products, "product_id"), rates.orphan_order_items
    )
    open_items, orphan_customers, orphan_oi, null_oi, stripped = plant_open_item_key_issues(
        seed, open_items, customer_ids, rates
    )
    record = PlantedIssues(
        duplicate_customers=pairs,
        orphan_product_ids=orphan_products,
        orphan_item_rows=orphan_items,
        orphan_customer_numbers=orphan_customers,
        orphan_open_item_rows=orphan_oi,
        null_key_open_item_rows=null_oi,
        stripped_zero_rows=stripped,
    )
    return customers, items, open_items, record
