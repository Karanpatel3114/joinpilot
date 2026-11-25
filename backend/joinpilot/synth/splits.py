"""Dataset splits from docs/data-model.md, and a command that writes all their gold.

Dev is for tuning; test is used only for the final run.

Usage:
    uv run python -m joinpilot.synth.splits --gold data/gold
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import NamedTuple

from joinpilot.config import get_settings
from joinpilot.synth.generate import build_dataset
from joinpilot.synth.gold import write_gold
from joinpilot.synth.naming import Naming

logger = logging.getLogger(__name__)


class DatasetSpec(NamedTuple):
    seed: int
    size: str
    naming: Naming

    @property
    def dataset_id(self) -> str:
        return f"erp_{self.size.lower()}{self.seed}_{self.naming}"


DEV: list[DatasetSpec] = [
    DatasetSpec(1, "S", "sap"),
    DatasetSpec(2, "S", "sap"),
    DatasetSpec(3, "S", "sap"),
    DatasetSpec(1, "S", "friendly"),
]
TEST: list[DatasetSpec] = [
    DatasetSpec(seed, size, naming)
    for seed in (101, 102, 103)
    for size in ("S", "M")
    for naming in ("sap", "friendly")
]
SPLITS: dict[str, list[DatasetSpec]] = {"dev": DEV, "test": TEST}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Write gold files for every split dataset.")
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--split", choices=["dev", "test", "all"], default="all")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_settings().synth
    specs = DEV + TEST if args.split == "all" else SPLITS[args.split]
    for spec in specs:
        dataset = build_dataset(spec.seed, spec.size, spec.naming, settings)
        write_gold(dataset, args.gold / dataset.dataset_id, settings)
        logger.info("gold written for %s", dataset.dataset_id)


if __name__ == "__main__":
    main()
