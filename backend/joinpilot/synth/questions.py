"""Gold question-answer pairs from templates, with parameters drawn from the data.

Questions use business words, never table names. Each answer is the exact result
set (columns and rows) computed in Python from the generated rows.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
from typing import Any

from joinpilot.synth.facts import Facts, money
from joinpilot.synth.rng import stream

COUNTRY_NAMES = {
    "US": "the United States",
    "DE": "Germany",
    "GB": "the United Kingdom",
    "FR": "France",
    "IN": "India",
}
MONTHS = [
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
]  # fmt: skip


def num(value: Decimal) -> str:
    """An exact amount answer, written as a two-decimal string like kpis.json (D-010)."""
    return money(value)


class QuestionSet:
    """Collects questions with sequential ids."""

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def add(
        self,
        template: str,
        question: str,
        columns: list[str],
        rows: list[list[Any]],
        *,
        ordered: bool = False,
        tags: tuple[str, ...] = (),
    ) -> None:
        self.items.append(
            {
                "id": f"q{len(self.items) + 1:03d}",
                "template": template,
                "question": question,
                "columns": columns,
                "rows": rows,
                "ordered": ordered,
                "tags": list(tags),
            }
        )


def gold_questions(seed: int, f: Facts) -> list[dict[str, Any]]:
    """Build about 40 questions with their true answers."""
    rng = stream(seed, "qa")
    qs = QuestionSet()
    ref = f.reference_date
    as_of = (
        f"as of {MONTHS[ref.month - 1]} {ref.day}, {ref.year} "
        "(the due date is the baseline date plus the payment days)"
    )

    def pick(options: list[Any], k: int) -> list[Any]:
        return [options[int(i)] for i in sorted(rng.choice(len(options), size=k, replace=False))]

    countries = Counter(c["country_code"] for c in f.customers)
    for code in pick(sorted(countries), 3):
        qs.add(
            "customers_in_country",
            f"How many customers are based in {COUNTRY_NAMES[code]}?",
            ["customer_count"],
            [[countries[code]]],
            tags=("duplicates",),
        )
    groups = Counter(p["product_group"] for p in f.products.values())
    for group in pick(sorted(groups), 2):
        qs.add(
            "products_in_group",
            f"How many products belong to product group {group}?",
            ["product_count"],
            [[groups[group]]],
        )
    months = Counter(h["order_date"][:6] for h in f.headers)
    for month in pick(sorted(months), 3):
        name = f"{MONTHS[int(month[4:]) - 1]} {month[:4]}"
        qs.add(
            "orders_in_month",
            f"How many sales orders were created in {name}?",
            ["order_count"],
            [[months[month]]],
        )
    for year in (2025, 2026):
        in_year = (h["net_value"] for h in f.headers if h["order_date"][:4] == str(year))
        total = sum(in_year, Decimal(0))
        qs.add(
            "order_value_year",
            f"What is the total net value of all sales orders created in {year}?",
            ["total_net_value"],
            [[num(total)]],
        )

    amounts = [r["amount"] for r in f.open_items]
    whole_ledger = ("orphans", "null_keys")  # answers that include orphan and null-key rows
    qs.add(
        "open_total",
        "What is the total amount of all open receivables?",
        ["open_amount"],
        [[num(sum(amounts, Decimal(0)))]],
        tags=whole_ledger,
    )
    over_90 = sum((r["amount"] for r in f.open_items if f.days_overdue(r) > 90), Decimal(0))
    qs.add(
        "open_over_90",
        f"What is the total open receivables amount more than 90 days overdue {as_of}?",
        ["overdue_amount"],
        [[num(over_90)]],
        tags=whole_ledger,
    )
    overdue: dict[str, Decimal] = defaultdict(Decimal)
    open_by_customer: dict[str, Decimal] = defaultdict(Decimal)
    for r in f.open_items:
        customer = f.master_customer(r["customer_id"])
        if customer:
            open_by_customer[customer] += r["amount"]
            if f.days_overdue(r) > 0:
                overdue[customer] += r["amount"]
    top5 = sorted(overdue.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    qs.add(
        "top_overdue_customers",
        "List the customer IDs and overdue amounts of the 5 customers with the highest "
        f"overdue receivables {as_of}, highest first.",
        ["customer_id", "overdue_amount"],
        [[cid, num(v)] for cid, v in top5],
        ordered=True,
        tags=("normalization",),
    )
    for cid in pick(sorted(open_by_customer), 3):
        qs.add(
            "customer_open_amount",
            f"What is the total open receivables amount for customer {cid}?",
            ["open_amount"],
            [[num(open_by_customer[cid])]],
            tags=("normalization",),
        )

    orphan_items = sum(1 for i in f.items if i["product_id"] not in f.products)
    qs.add(
        "orphan_items",
        "How many sales order items reference a product that does not exist in the product master?",
        ["item_count"],
        [[orphan_items]],
        tags=("orphans",),
    )
    order_year = f.order_year()
    revenue_2026: dict[str, Decimal] = defaultdict(Decimal)
    product_revenue_2026: dict[str, Decimal] = defaultdict(Decimal)
    for item in f.items:
        if order_year[item["order_id"]] == 2026:
            product_revenue_2026[item["product_id"]] += item["net_value"]
            product = f.products.get(item["product_id"])
            if product:
                revenue_2026[product["product_group"]] += item["net_value"]
    for group in pick(sorted(revenue_2026), 3):
        qs.add(
            "revenue_group_2026",
            f"What was the total item net value in 2026 for products in product group {group}?",
            ["revenue"],
            [[num(revenue_2026[group])]],
        )
    best_group = max(sorted(revenue_2026), key=lambda g: revenue_2026[g])
    qs.add(
        "top_group_2026",
        "Which product group had the highest total item net value in 2026?",
        ["product_group"],
        [[best_group]],
    )

    name_counts = Counter(c["customer_name"] for c in f.customers)
    orders_2026 = Counter(h["customer_id"] for h in f.headers if h["order_date"][:4] == "2026")
    unique_named = sorted(
        c["customer_id"]
        for c in f.customers
        if name_counts[c["customer_name"]] == 1 and orders_2026[c["customer_id"]] > 0
    )
    names = {c["customer_id"]: c["customer_name"] for c in f.customers}
    for cid in pick(unique_named, 3):
        qs.add(
            "customer_orders_2026",
            f"How many sales orders did {names[cid]} place in 2026?",
            ["order_count"],
            [[orders_2026[cid]]],
        )
    qs.add(
        "avg_items_per_order",
        "What is the average number of items per sales order?",
        ["avg_items"],
        [[round(len(f.items) / len(f.headers), 6)]],
    )
    qs.add(
        "eur_open_items",
        "How many open receivable line items are in EUR?",
        ["item_count"],
        [[sum(1 for r in f.open_items if r["currency"] == "EUR")]],
        tags=whole_ledger,
    )
    orgs = Counter(h["sales_org"] for h in f.headers)
    qs.add(
        "orders_per_sales_org",
        "How many sales orders does each sales organization have?",
        ["sales_org", "order_count"],
        [[org, orgs[org]] for org in sorted(orgs)],
    )
    qs.add(
        "top_country_customers",
        "Which country code has the most customers?",
        ["country_code"],
        [[countries.most_common(1)[0][0]]],
    )
    with_open = set(open_by_customer)
    qs.add(
        "customers_without_open_items",
        "How many customers in the customer master have no open receivables?",
        ["customer_count"],
        [[sum(1 for c in f.customers if c["customer_id"] not in with_open)]],
        tags=("normalization",),
    )
    quantity: dict[str, int] = defaultdict(int)
    for item in f.items:
        if item["product_id"] in f.products:
            quantity[item["product_id"]] += item["quantity"]
    for pid in pick(sorted(quantity), 2):
        qs.add(
            "product_quantity",
            f"What is the total ordered quantity of product {pid}?",
            ["total_quantity"],
            [[quantity[pid]]],
        )
    customers_by_month: dict[str, set[str]] = defaultdict(set)
    for h in f.headers:
        customers_by_month[h["order_date"][:6]].add(h["customer_id"])
    for month in pick(sorted(customers_by_month), 2):
        name = f"{MONTHS[int(month[4:]) - 1]} {month[:4]}"
        qs.add(
            "distinct_customers_month",
            f"How many distinct customers placed sales orders in {name}?",
            ["customer_count"],
            [[len(customers_by_month[month])]],
        )
    top3 = sorted(product_revenue_2026.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    qs.add(
        "top_products_2026",
        "List the product IDs and total item net value of the 3 products with the highest "
        "item net value in 2026, highest first.",
        ["product_id", "revenue"],
        [[pid, num(v)] for pid, v in top3],
        ordered=True,
    )
    qs.add(
        "largest_open_item",
        "What is the largest single open receivable line amount?",
        ["max_amount"],
        [[num(max(amounts))]],
        tags=whole_ledger,
    )
    qs.add(
        "not_due_count",
        f"How many open receivable line items are not yet due {as_of}?",
        ["item_count"],
        [[sum(1 for r in f.open_items if f.days_overdue(r) <= 0)]],
        tags=whole_ledger,
    )
    values = sorted(h["net_value"] for h in f.headers)
    for quantile in (0.5, 0.9):
        threshold = Decimal(int(values[int(quantile * len(values))]) // 1000 * 1000)
        qs.add(
            "big_orders",
            f"How many sales orders have a net value above {threshold:.0f}?",
            ["order_count"],
            [[sum(1 for v in values if v > threshold)]],
        )
    qs.add(
        "duplicate_customer_names",
        "How many customer names appear more than once in the customer master?",
        ["name_count"],
        [[sum(1 for count in name_counts.values() if count > 1)]],
        tags=("duplicates",),
    )
    qs.add(
        "open_items_without_customer",
        "How many open receivable line items have no customer number?",
        ["item_count"],
        [[sum(1 for r in f.open_items if r["customer_id"] is None)]],
        tags=("null_keys",),
    )
    return qs.items
