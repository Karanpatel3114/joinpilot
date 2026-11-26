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
from pathlib import Path
from typing import Any

from eval.baselines import inclusion_dependency, name_only, overlap_only
from eval.datasets import EvalDataset, load_dataset, split_ids
from eval.gold import GOLD_ROOT, load_joins
from eval.join_metrics import JoinCounts, PredictedEdge, score_dataset
from eval.kpi_eval import evaluate_kpis
from eval.llm_systems import joinpilot_full, llm_only, requirement_for
from eval.qa_eval import evaluate_qa
from eval.redteam_eval import evaluate_redteam
from eval.results import new_report, write_results
from eval.views_eval import evaluate_views
from joinpilot.config import Settings, get_settings
from joinpilot.errors import LLMUnavailableError
from joinpilot.joins.scoring import score_candidates
from joinpilot.llm.factory import make_base_provider, make_provider
from joinpilot.llm.observed import ObservedProvider, UsageLog
from joinpilot.llm.prompts import PROMPTS_DIR
from joinpilot.profiling.models import ProjectProfile

logger = logging.getLogger(__name__)
System = Callable[[ProjectProfile], list[PredictedEdge]]


def joinpilot_deterministic(profile: ProjectProfile) -> list[PredictedEdge]:
    """JoinPilot's accepted candidates, with no LLM."""
    return [
        PredictedEdge(
            c.from_,
            c.to,
            c.normalization,
            c.fan_out_risk,
            (c.filter.column, c.filter.value) if c.filter else None,
        )
        for c in score_candidates(profile, get_settings().joins)
        if c.accepted
    ]


JOIN_SYSTEMS: dict[str, System] = {
    "name_only": name_only,
    "overlap_only": overlap_only,
    "inclusion_dependency": inclusion_dependency,
    "joinpilot_deterministic": joinpilot_deterministic,
}


def evaluate_joins(datasets: list[EvalDataset], gold_root: Path = GOLD_ROOT) -> dict[str, Any]:
    """Score every system on every dataset; aggregate by summing counts (micro-average)."""
    results: dict[str, Any] = {}
    for system, predict in JOIN_SYSTEMS.items():
        total = JoinCounts()
        per_dataset = {}
        for dataset in datasets:
            gold = load_joins(dataset.dataset_id, gold_root)
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


def spread(values: list[float | None]) -> dict[str, float] | None:
    """Mean and range over repeated runs (eval-plan: report both); None if never defined."""
    known = [v for v in values if v is not None]
    if not known:
        return None
    return {
        "mean": round(sum(known) / len(known), 4),
        "min": round(min(known), 4),
        "max": round(max(known), 4),
    }


SUMMARY_METRICS = (
    "precision",
    "recall",
    "f1",
    "normalization_recall",
    "fan_out_recall",
    "decoy_rejection",
)


def run_llm_system(
    name: str, datasets: list[EvalDataset], settings: Settings, gold_root: Path
) -> dict[str, Any]:
    """One run of one LLM system over every dataset, with failures recorded, not hidden."""
    log = UsageLog()
    llm = ObservedProvider(make_base_provider(settings), settings.llm, log=log)
    total = JoinCounts()
    per_dataset: dict[str, Any] = {}
    for dataset in datasets:
        diagnostics: dict[str, Any] = {}
        try:
            if name == "llm_only":
                predicted = llm_only(dataset.profile, llm)
            else:
                requirement = requirement_for(dataset.dataset_id)
                predicted, diagnostics = joinpilot_full(dataset.profile, llm, settings, requirement)
        except LLMUnavailableError as error:
            predicted, diagnostics = [], {"failed": error.message}
        counts = score_dataset(
            dataset.dataset_id, predicted, load_joins(dataset.dataset_id, gold_root)
        )
        per_dataset[dataset.dataset_id] = {"metrics": counts.metrics(), "diagnostics": diagnostics}
        total.add(counts)
    return {
        "aggregate": total.metrics(),
        "per_dataset": per_dataset,
        "usage": log.totals(),
        "false_positives": total.false_positives,
        "false_negatives": total.false_negatives,
    }


def evaluate_llm_joins(
    datasets: list[EvalDataset], settings: Settings, runs: int, gold_root: Path = GOLD_ROOT
) -> dict[str, Any]:
    """Run each LLM system `runs` times without the cache; report every run, mean and range."""
    results: dict[str, Any] = {}
    for name in ("llm_only", "joinpilot_full"):
        per_run = [
            {"run": i + 1, **run_llm_system(name, datasets, settings, gold_root)}
            for i in range(runs)
        ]
        results[name] = {
            "runs": per_run,
            "summary": {k: spread([r["aggregate"][k] for r in per_run]) for k in SUMMARY_METRICS},
        }
    return results


def main(argv: list[str] | None = None) -> None:
    """Command line entry point; see the module docstring."""
    parser = argparse.ArgumentParser(description="Run JoinPilot's evaluation.")
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--llm", action="store_true", help="also run the LLM systems")
    parser.add_argument("--runs", type=int, default=3, help="repeats for LLM systems")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_settings()
    profiling = settings.profiling
    report = new_report(args.split)
    report["settings"] = {
        "profiling": profiling.model_dump(mode="json"),
        "joins": settings.joins.model_dump(mode="json"),
    }
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
    report["settings"]["checks"] = settings.checks.model_dump(mode="json")
    report["settings"]["kpi"] = settings.kpi.model_dump(mode="json")
    report["views"] = evaluate_views(datasets, settings)
    report["kpis"] = evaluate_kpis(datasets, settings)
    logger.info("kpis: %s", json.dumps(report["kpis"]["aggregate"]))
    report["redteam"] = evaluate_redteam()
    if args.llm:
        report["settings"]["llm"] = settings.llm.model_dump(mode="json")
        report["settings"]["agent"] = settings.agent.model_dump(mode="json")
        report["prompts"] = sorted(p.name for p in PROMPTS_DIR.glob("*.md"))
        report["requirements"] = {d.dataset_id: requirement_for(d.dataset_id) for d in datasets}
        try:
            report["llm_joins"] = evaluate_llm_joins(datasets, settings, args.runs)
        except LLMUnavailableError as error:
            logger.error("LLM systems skipped: %s", error.message)
            report["llm_joins"] = {"skipped": error.message}
        qa_log = UsageLog()
        try:
            report["qa"] = evaluate_qa(datasets, settings, make_provider(settings, qa_log))
            report["qa"]["usage"] = qa_log.totals()
            logger.info("qa: %s", json.dumps(report["qa"]["aggregate"]))
        except LLMUnavailableError as error:
            logger.error("question answering skipped: %s", error.message)
            report["qa"] = {"skipped": error.message}
    for system, result in report["joins"].items():
        logger.info("%s: %s", system, json.dumps(result["aggregate"]))
    logger.info("results written to %s", write_results(report))


if __name__ == "__main__":
    main()
