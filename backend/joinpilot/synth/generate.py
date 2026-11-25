"""Write a synthetic ERP dataset to Parquet, plus optional gold.

Usage:
    uv run python -m joinpilot.synth.generate --seed 1 --size S --naming sap \
        --out data/generated/erp_s1_sap [--gold data/gold]
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pyarrow.parquet as pq

from joinpilot.config import SynthSettings, get_settings
from joinpilot.synth.dataset import GENERATOR_VERSION, ErpDataset, build_dataset, fingerprint
from joinpilot.synth.gold import write_gold
from joinpilot.synth.naming import NAMING_MODES

logger = logging.getLogger(__name__)


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
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> None:
    """Command line entry point; see the module docstring."""
    parser = argparse.ArgumentParser(description="Generate a synthetic ERP dataset.")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--size", choices=sorted(SynthSettings().sizes), default="S")
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
