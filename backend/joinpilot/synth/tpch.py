"""TPC-H tables from DuckDB's tpch extension, with the standard foreign-key graph as gold.

The data is generated locally with DuckDB's dbgen. Results on it are not official,
audited TPC-H results.

Usage:
    uv run python -m joinpilot.synth.tpch --sf 0.1 --out data/generated/tpch_sf0.1 --gold data/gold
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import duckdb

logger = logging.getLogger(__name__)

TPCH_TABLES = ("region", "nation", "supplier", "customer", "part", "partsupp", "orders", "lineitem")

# Single-column foreign keys (many side first).
TPCH_FOREIGN_KEYS: list[tuple[str, str]] = [
    ("nation.n_regionkey", "region.r_regionkey"),
    ("supplier.s_nationkey", "nation.n_nationkey"),
    ("customer.c_nationkey", "nation.n_nationkey"),
    ("partsupp.ps_partkey", "part.p_partkey"),
    ("partsupp.ps_suppkey", "supplier.s_suppkey"),
    ("orders.o_custkey", "customer.c_custkey"),
    ("lineitem.l_orderkey", "orders.o_orderkey"),
    ("lineitem.l_partkey", "part.p_partkey"),
    ("lineitem.l_suppkey", "supplier.s_suppkey"),
]
# Two-column foreign key: lineitem (part, supplier) -> partsupp.
TPCH_COMPOSITE_KEYS: list[tuple[list[str], list[str]]] = [
    (["lineitem.l_partkey", "lineitem.l_suppkey"], ["partsupp.ps_partkey", "partsupp.ps_suppkey"]),
]


def dataset_id(scale_factor: float) -> str:
    """Name a TPC-H dataset like `tpch_sf0.1`."""
    return f"tpch_sf{scale_factor:g}"


def generate_tpch(scale_factor: float, out_dir: Path) -> dict[str, Any]:
    """Run dbgen in a scratch DuckDB and write one Parquet file per table."""
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        con.execute("INSTALL tpch")
        con.execute("LOAD tpch")
        con.execute("CALL dbgen(sf = ?)", [scale_factor])
        rows: dict[str, int] = {}
        for table in TPCH_TABLES:
            target = (out_dir / f"{table}.parquet").as_posix()
            con.execute(f"COPY {table} TO '{target}' (FORMAT parquet, COMPRESSION zstd)")
            count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            rows[table] = int(count[0]) if count else 0
    finally:
        con.close()
    manifest: dict[str, Any] = {
        "dataset_id": dataset_id(scale_factor),
        "source": "DuckDB tpch extension (dbgen)",
        "scale_factor": scale_factor,
        "tables": {t: {"rows": n, "file": f"{t}.parquet"} for t, n in rows.items()},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def tpch_gold(scale_factor: float) -> dict[str, Any]:
    """The standard TPC-H foreign-key graph in the same shape as the ERP joins gold."""
    return {
        "dataset_id": dataset_id(scale_factor),
        "edges": [
            {
                "from": source,
                "to": target,
                "cardinality": "N:1",
                "normalization": "none",
                "fan_out": False,
                "filter": None,
                "orphan_rows": 0,
                "null_rows": 0,
            }
            for source, target in TPCH_FOREIGN_KEYS
        ],
        "composite_edges": [{"from": f, "to": t} for f, t in TPCH_COMPOSITE_KEYS],
        "decoys": [],
    }


def main(argv: list[str] | None = None) -> None:
    """Command line entry point; see the module docstring."""
    parser = argparse.ArgumentParser(description="Generate TPC-H tables and their gold graph.")
    parser.add_argument("--sf", type=float, default=0.1)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--gold", type=Path, help="gold root folder")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.out:
        manifest = generate_tpch(args.sf, args.out)
        logger.info("wrote %s to %s", manifest["dataset_id"], args.out)
    if args.gold:
        folder = args.gold / dataset_id(args.sf)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "joins.json").write_text(json.dumps(tpch_gold(args.sf), indent=2) + "\n")
        logger.info("wrote gold for %s", dataset_id(args.sf))


if __name__ == "__main__":
    main()
