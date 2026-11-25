"""Generated rows as plain Python values, plus the business rules gold is computed with."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from joinpilot.config import SynthSettings
from joinpilot.synth.dataset import ErpDataset

AGING_BUCKETS = ("not_due", "1-30", "31-60", "61-90", "90+")


@dataclass(frozen=True)
class Facts:
    """Generated rows as plain Python dicts, with helper lookups."""

    customers: list[dict[str, Any]]
    products: dict[str, dict[str, Any]]
    headers: list[dict[str, Any]]
    items: list[dict[str, Any]]
    open_items: list[dict[str, Any]]
    reference_date: date
    customer_ids: frozenset[str]

    @classmethod
    def from_dataset(cls, dataset: ErpDataset, settings: SynthSettings) -> Facts:
        """Convert a dataset's canonical tables to plain rows once."""
        c = dataset.canonical
        products = {r["product_id"]: r for r in c["products"].to_pylist()}
        customers = c["customers"].to_pylist()
        return cls(
            customers=customers,
            products=products,
            headers=c["order_headers"].to_pylist(),
            items=c["order_items"].to_pylist(),
            open_items=c["open_items"].to_pylist(),
            reference_date=settings.reference_date,
            customer_ids=frozenset(r["customer_id"] for r in customers),
        )

    def master_customer(self, stored_key: str | None) -> str | None:
        """Map an open item's stored key to a master customer id, if one exists."""
        if stored_key is None:
            return None
        padded = stored_key.zfill(10)
        return padded if padded in self.customer_ids else None

    def days_overdue(self, row: dict[str, Any]) -> int:
        """Reference date minus due date (baseline date + payment days), in days."""
        due = row["baseline_date"] + timedelta(days=row["payment_days"])
        return int((self.reference_date - due).days)

    def order_year(self) -> dict[str, int]:
        """Map each order id to the year of its (text) order date."""
        return {h["order_id"]: int(h["order_date"][:4]) for h in self.headers}


def aging_bucket(days_overdue: int) -> str:
    """Bucket by days past the due date; due today or later is `not_due`."""
    if days_overdue <= 0:
        return "not_due"
    for upper, label in ((30, "1-30"), (60, "31-60"), (90, "61-90")):
        if days_overdue <= upper:
            return label
    return "90+"


def money(value: Decimal) -> str:
    """Format an exact amount with two decimals, as a string (never a float)."""
    return f"{value:.2f}"
