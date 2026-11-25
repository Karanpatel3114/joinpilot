"""Run the evaluation on a split.

Usage:
    uv run python -m eval.run_all --split dev
The test split runs only when the owner asks for the final run.
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Callable
from typing import Any

from eval.baselines import name_only, overlap_only
from eval.datasets import EvalDataset, load_dataset, split_ids
from eval.gold import load_joins
from eval.join_metrics import JoinCounts, PredictedEdge, score_dataset
from eval.results import new_report, write_results
from joinpilot.config import get_settings
from joinpilot.joins.scoring import score_candidates
from joinpilot.profiling.models import ProjectProfile

logger = logging.getLogger(__name__)
System = Callable[[ProjectProfile], list[PredictedEdge]]


def joinpilot_deterministic(profile: ProjectProfile) -> list[PredictedEdge]:
    """JoinPilot's accepted candidates, with no LLM."""
    return [
        PredictedEdge(c.from_, c.to, c.normalization, c.fan_out_risk)
        for c in score_candidates(profile, get_settings().joins)
        if c.accepted
    ]


JOIN_SYSTEMS: dict[str, System] = {
    "name_only": name_only,
    "overlap_only": overlap_only,
    "joinpilot_deterministic": joinpilot_deterministic,
}


def evaluate_joins(datasets: list[EvalDataset]) -> dict[str, Any]:
    """Score every system on every dataset; aggregate by summing counts (micro-average)."""
    results: dict[str, Any] = {}
    for system, predict in JOIN_SYSTEMS.items():
        total = JoinCounts()
        per_dataset = {}
        for dataset in datasets:
            gold = load_joins(dataset.dataset_id)
            counts = score_dataset(dataset.dataset_id, predict(dataset.profile), gold)
            per_dataset[dataset.dataset_id] = counts.metrics()
            total.add(counts)
        results[system] = {
            "aggregate": total.metrics(),
            "per_dataset": per_dataset,
            "false_positives": total.false_positives,
            "false_negatives": total.false_negatives,
        }
    return results


def main(argv: list[str] | None = None) -> None:
    """Command line entry point; see the module docstring."""
    parser = argparse.ArgumentParser(description="Run JoinPilot's evaluation.")
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    profiling = get_settings().profiling
    report = new_report(args.split)
    if report["dirty"]:
        logger.warning("the working tree has uncommitted changes; results will say so")
    datasets = [load_dataset(i, profiling) for i in split_ids(args.split)]
    report["datasets"] = [
        {
            "dataset_id": d.dataset_id,
            "fingerprint": d.fingerprint,
            "profile_seconds": round(d.profile_seconds, 3),
        }
        for d in datasets
    ]
    report["joins"] = evaluate_joins(datasets)
    for system, result in report["joins"].items():
        logger.info("%s: %s", system, json.dumps(result["aggregate"]))
    logger.info("results written to %s", write_results(report))


if __name__ == "__main__":
    main()
