"""Assemble a full synthetic ERP dataset and write it to Parquet, plus optional gold.

Usage:
    uv run python -m joinpilot.synth.generate --seed 1 --size S --naming sap \
        --out data/generated/erp_s1_sap [--gold data/gold]
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from joinpilot.config import SynthSettings, get_settings
from joinpilot.synth.issues import PlantedIssues, plant_issues
from joinpilot.synth.masters import make_customers, make_products
from joinpilot.synth.naming import NAMING_MODES, Naming, rename
from joinpilot.synth.orders import make_orders
from joinpilot.synth.receivables import make_open_items

logger = logging.getLogger(__name__)
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


def write_dataset(dataset: ErpDataset, out_dir: Path) -> dict[str, object]:
    """Write one Parquet file per table and a manifest; return the manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tables = dataset.output_tables()
    for name, table in tables.items():
        pq.write_table(table, out_dir / f"{name}.parquet", compression="zstd")
    manifest: dict[str, object] = {
        "dataset_id": dataset.dataset_id,
        "seed": dataset.seed,
        "size": dataset.size,
        "naming": dataset.naming,
        "generator_version": GENERATOR_VERSION,
        "tables": {
            name: {"rows": t.num_rows, "file": f"{name}.parquet"} for name, t in tables.items()
        },
        "fingerprint": fingerprint(tables),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv: list[str] | None = None) -> None:
    from joinpilot.synth.gold import write_gold

    parser = argparse.ArgumentParser(description="Generate a synthetic ERP dataset.")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--size", choices=["S", "M", "L"], default="S")
    parser.add_argument("--naming", choices=NAMING_MODES, default="sap")
    parser.add_argument("--out", type=Path, help="output folder for Parquet files")
    parser.add_argument("--gold", type=Path, help="gold root folder (writes <gold>/<dataset_id>/)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    settings = get_settings().synth
    dataset = build_dataset(args.seed, args.size, args.naming, settings)
    if args.out:
        manifest = write_dataset(dataset, args.out)
        logger.info("wrote %s to %s (%s)", dataset.dataset_id, args.out, manifest["fingerprint"])
    if args.gold:
        write_gold(dataset, args.gold / dataset.dataset_id, settings)
        logger.info("wrote gold for %s", dataset.dataset_id)


if __name__ == "__main__":
    main()
