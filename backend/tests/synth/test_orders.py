from collections import defaultdict
from decimal import Decimal

import pytest

from joinpilot.config import SynthSettings
from joinpilot.synth.masters import make_customers, make_products
from joinpilot.synth.orders import Orders, make_orders


@pytest.fixture(scope="module")
def orders() -> Orders:
    settings = SynthSettings()
    return make_orders(1, 2_000, make_customers(1, 200), make_products(1, 300), settings)


def test_order_ids_are_unique_10_character_strings(orders: Orders) -> None:
    ids = orders.headers.column("order_id").to_pylist()
    assert len(set(ids)) == len(ids) == 2_000
    assert all(len(i) == 10 for i in ids)


def test_order_dates_are_yyyymmdd_text_in_range(orders: Orders) -> None:
    dates = orders.headers.column("order_date").to_pylist()
    assert all(isinstance(d, str) and len(d) == 8 for d in dates)
    assert min(dates) >= "20250101"
    assert max(dates) <= "20260630"


def test_items_reference_real_orders_and_number_from_one(orders: Orders) -> None:
    order_ids = set(orders.headers.column("order_id").to_pylist())
    per_order: dict[str, list[int]] = defaultdict(list)
    for row in orders.items.to_pylist():
        assert row["order_id"] in order_ids
        per_order[row["order_id"]].append(row["item_no"])
    assert set(per_order) == order_ids
    assert all(nos == list(range(1, len(nos) + 1)) for nos in per_order.values())
    assert all(1 <= len(nos) <= 5 for nos in per_order.values())


def test_header_value_is_exact_sum_of_item_values(orders: Orders) -> None:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for row in orders.items.to_pylist():
        totals[row["order_id"]] += row["net_value"]
    for row in orders.headers.to_pylist():
        assert row["net_value"] == totals[row["order_id"]]


def test_currency_mix_is_mostly_usd_with_some_eur(orders: Orders) -> None:
    currencies = orders.headers.column("currency").to_pylist()
    eur_share = currencies.count("EUR") / len(currencies)
    assert set(currencies) == {"USD", "EUR"}
    assert 0.05 < eur_share < 0.15
