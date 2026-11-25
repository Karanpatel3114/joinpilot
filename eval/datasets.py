"""Build each split dataset, check it matches its gold, and profile it with the app's code."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import duckdb
import pyarrow.parquet as pq

from eval.gold import load_manifest
from joinpilot.config import REPO_ROOT, ProfilingSettings, SynthSettings
from joinpilot.profiling.loader import load_arrow
from joinpilot.profiling.models import ProjectProfile
from joinpilot.profiling.service import profile_project
from joinpilot.synth.dataset import build_dataset, fingerprint
from joinpilot.synth.splits import SPLITS
from joinpilot.synth.tpch import TPCH_TABLES, generate_tpch

logger = logging.getLogger(__name__)
TPCH_ID = "tpch_sf0.1"
TPCH_DIR = REPO_ROOT / "data" / "generated" / TPCH_ID


class GoldMismatchError(RuntimeError):
    """The regenerated data is not the data the gold was computed from."""


@dataclass
class EvalDataset:
    """One loaded and profiled dataset, ready for every system to be scored on."""

    dataset_id: str
    fingerprint: str
    con: duckdb.DuckDBPyConnection
    profile: ProjectProfile
    profile_seconds: float


def split_ids(split: str) -> list[str]:
    """Dataset ids in a split; the test split also includes TPC-H."""
    ids = [spec.dataset_id for spec in SPLITS[split]]
    return [*ids, TPCH_ID] if split == "test" else ids


def load_dataset(dataset_id: str, profiling: ProfilingSettings) -> EvalDataset:
    """Generate (or reuse) the dataset in an in-memory DuckDB and profile it."""
    con = duckdb.connect()
    if dataset_id == TPCH_ID:
        if not (TPCH_DIR / "manifest.json").exists():
            generate_tpch(0.1, TPCH_DIR)
        tables = {t: pq.read_table(TPCH_DIR / f"{t}.parquet") for t in TPCH_TABLES}
        data_fingerprint = fingerprint(tables)
        for name, data in tables.items():
            load_arrow(con, name, data)
        names = list(tables)
    else:
        spec = next(s for split in SPLITS.values() for s in split if s.dataset_id == dataset_id)
        tables = build_dataset(spec.seed, spec.size, spec.naming, SynthSettings()).output_tables()
        data_fingerprint = fingerprint(tables)
        manifest = load_manifest(dataset_id)
        if manifest is None:
            raise GoldMismatchError(f"{dataset_id}: gold has no manifest to check the data against")
        if manifest["fingerprint"] != data_fingerprint:
            raise GoldMismatchError(f"{dataset_id}: data fingerprint differs from its gold")
        for name, data in tables.items():
            load_arrow(con, name, data)
        names = list(tables)
    started = time.perf_counter()
    profile = profile_project(con, {name: name for name in names}, profiling)
    elapsed = time.perf_counter() - started
    logger.info("profiled %s in %.2fs", dataset_id, elapsed)
    return EvalDataset(dataset_id, data_fingerprint, con, profile, elapsed)
