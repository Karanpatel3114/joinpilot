from typing import Any

import pytest

from joinpilot.config import IssueRates, SynthSettings
from joinpilot.synth.issues import PlantedIssues, plant_issues
from joinpilot.synth.masters import make_customers, make_products
from joinpilot.synth.orders import make_orders
from joinpilot.synth.receivables import make_open_items

SETTINGS = SynthSettings()


def build(rates: IssueRates) -> tuple[Any, Any, Any, Any, PlantedIssues]:
    customers = make_customers(1, 1_000)
    master = make_products(1, 2_000)
    orders = make_orders(1, 3_000, customers, master, SETTINGS)
    open_items = make_open_items(1, 4_000, customers, SETTINGS)
    c, items, oi, record = plant_issues(
        1, customers, master.products, orders.items, open_items, rates
    )
    return customers, master.products, (c, items, oi), orders.items, record


@pytest.fixture(scope="module")
def planted() -> tuple[Any, Any, Any, Any, PlantedIssues]:
    return build(IssueRates())


def test_duplicate_customers_share_a_name_but_not_an_id(planted: Any) -> None:
    _, _, (customers, _, _), _, record = planted
    rows = {r["customer_id"]: r for r in customers.to_pylist()}
    assert len(record.duplicate_customers) == 5
    for dup_id, original_id in record.duplicate_customers:
        assert dup_id != original_id
        assert rows[dup_id]["customer_name"] == rows[original_id]["customer_name"]


def test_orphan_items_point_to_products_missing_from_the_master(planted: Any) -> None:
    _, products, (_, items, _), clean_items, record = planted
    product_ids = set(products.column("product_id").to_pylist())
    orphans = [p for p in items.column("product_id").to_pylist() if p not in product_ids]
    assert len(orphans) == record.orphan_item_rows == round(0.01 * clean_items.num_rows)
    assert set(orphans) <= set(record.orphan_product_ids)
    assert all(len(p) == 18 for p in orphans)


def test_open_item_keys_lose_leading_zeros_and_include_orphans_and_nulls(
    planted: Any,
) -> None:
    customers, _, (_, _, open_items), _, record = planted
    master = {str(int(c)) for c in customers.column("customer_id").to_pylist()}
    keys = open_items.column("customer_id").to_pylist()
    non_null = [k for k in keys if k is not None]
    assert keys.count(None) == record.null_key_open_item_rows == 12
    assert all(not k.startswith("0") for k in non_null)
    orphans = [k for k in non_null if k not in master]
    assert len(orphans) == record.orphan_open_item_rows == 20
    assert record.stripped_zero_rows == len(non_null)


def test_rates_come_from_config_and_zero_rates_plant_nothing() -> None:
    zero = IssueRates(
        orphan_order_items=0,
        orphan_open_items=0,
        duplicate_customers=0,
        null_key_open_items=0,
        stripped_zeros_open_items=0,
    )
    customers, _, (_, _, open_items), _, record = build(zero)
    master = set(customers.column("customer_id").to_pylist())
    assert record.duplicate_customers == []
    assert record.orphan_item_rows == record.orphan_open_item_rows == 0
    assert set(open_items.column("customer_id").to_pylist()) <= master
