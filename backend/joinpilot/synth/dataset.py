"""One synthetic ERP dataset: build every table for a seed, size and naming mode."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

import pyarrow as pa
import pyarrow.csv as pacsv

from joinpilot.config import SynthSettings
from joinpilot.synth.issues import PlantedIssues, plant_issues
from joinpilot.synth.masters import make_customers, make_products
from joinpilot.synth.naming import Naming, rename
from joinpilot.synth.orders import make_orders
from joinpilot.synth.receivables import make_open_items

GENERATOR_VERSION = "1"


@dataclass(frozen=True)
class ErpDataset:
    """One generated dataset, kept with canonical (friendly) names internally."""

    dataset_id: str
    seed: int
    size: str
    naming: Naming
    canonical: dict[str, pa.Table]
    planted: PlantedIssues

    def output_tables(self) -> dict[str, pa.Table]:
        """Return the tables renamed for this dataset's naming mode."""
        return dict(rename(name, table, self.naming) for name, table in self.canonical.items())


def make_dataset_id(seed: int, size: str, naming: Naming) -> str:
    """Name a dataset like `erp_s1_sap`: size letter, seed, naming mode."""
    return f"erp_{size.lower()}{seed}_{naming}"


def build_dataset(seed: int, size: str, naming: Naming, settings: SynthSettings) -> ErpDataset:
    """Generate every table for one seed and size, with issues planted."""
    spec = settings.sizes[size]
    customers = make_customers(seed, spec.customers)
    master = make_products(seed, spec.products)
    orders = make_orders(seed, spec.orders, customers, master, settings)
    open_items = make_open_items(seed, spec.open_items, customers, settings)
    customers, items, open_items, planted = plant_issues(
        seed, customers, master.products, orders.items, open_items, settings.issues
    )
    canonical = {
        "customers": customers,
        "products": master.products,
        "product_texts": master.texts,
        "order_headers": orders.headers,
        "order_items": items,
        "open_items": open_items,
    }
    return ErpDataset(make_dataset_id(seed, size, naming), seed, size, naming, canonical, planted)


def fingerprint(tables: dict[str, pa.Table]) -> str:
    """Hash table names, schemas and rows (as CSV text) into one stable fingerprint."""
    digest = hashlib.sha256()
    for name in sorted(tables):
        buffer = io.BytesIO()
        pacsv.write_csv(tables[name], buffer)
        digest.update(name.encode())
        digest.update(str(tables[name].schema).encode())
        digest.update(buffer.getvalue())
    return f"sha256:{digest.hexdigest()}"
