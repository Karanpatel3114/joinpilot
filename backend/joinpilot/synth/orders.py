"""Sales order headers and items.

Order dates are stored as `YYYYMMDD` text on purpose (a common ERP habit), and a
header's net value is the exact sum of its items' net values.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyarrow as pa

from joinpilot.config import SynthSettings
from joinpilot.synth.masters import ProductMaster
from joinpilot.synth.money import money_array
from joinpilot.synth.rng import random_dates, stream, zipf_weights

FIRST_ORDER_NUMBER = 5_000_000
DISCOUNTS = np.array([0.0, 0.05, 0.10, 0.15])
EU_COUNTRIES = {"DE", "FR"}


@dataclass(frozen=True)
class Orders:
    headers: pa.Table
    items: pa.Table


def popularity(rng: np.random.Generator, n: int) -> np.ndarray:
    """Zipf-like pick weights assigned to entities in a random order."""
    return zipf_weights(n)[rng.permutation(n)]


def make_orders(
    seed: int,
    n_orders: int,
    customers: pa.Table,
    products: ProductMaster,
    settings: SynthSettings,
) -> Orders:
    """Generate order headers and 1 to `max_items_per_order` items per order."""
    rng = stream(seed, "orders")
    customer_ids = customers.column("customer_id").to_pylist()
    countries = customers.column("country_code").to_pylist()
    product_ids = products.products.column("product_id").to_pylist()

    order_ids = [str(FIRST_ORDER_NUMBER + i).zfill(10) for i in range(n_orders)]
    dates = sorted(random_dates(rng, settings.order_start, settings.order_end, n_orders))
    cust_idx = rng.choice(len(customer_ids), size=n_orders, p=popularity(rng, len(customer_ids)))
    currencies = np.where(rng.random(n_orders) < settings.eur_share, "EUR", "USD")
    item_counts = rng.integers(1, settings.max_items_per_order + 1, size=n_orders)

    n_items = int(item_counts.sum())
    prod_idx = rng.choice(len(product_ids), size=n_items, p=popularity(rng, len(product_ids)))
    quantities = rng.integers(1, 21, size=n_items)
    discounts = DISCOUNTS[rng.integers(len(DISCOUNTS), size=n_items)]
    item_cents = np.round(
        quantities * products.list_price_cents[prod_idx] * (1.0 - discounts)
    ).astype(np.int64)

    item_order_pos = np.repeat(np.arange(n_orders), item_counts)
    item_numbers = np.concatenate([np.arange(1, k + 1) for k in item_counts])
    header_cents = np.bincount(item_order_pos, weights=item_cents, minlength=n_orders)

    headers = pa.table(
        {
            "order_id": order_ids,
            "order_date": [d.strftime("%Y%m%d") for d in dates],
            "customer_id": [customer_ids[i] for i in cust_idx],
            "sales_org": ["2000" if countries[i] in EU_COUNTRIES else "1000" for i in cust_idx],
            "currency": currencies.tolist(),
            "net_value": money_array(np.round(header_cents).astype(np.int64)),
        }
    )
    items = pa.table(
        {
            "order_id": [order_ids[i] for i in item_order_pos],
            "item_no": pa.array(item_numbers, pa.int32()),
            "product_id": [product_ids[i] for i in prod_idx],
            "quantity": pa.array(quantities, pa.int32()),
            "net_value": money_array(item_cents),
        }
    )
    return Orders(headers, items)
