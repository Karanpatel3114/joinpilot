"""Write evaluation results with the split, datasets, fingerprints, commit and date."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from joinpilot.config import REPO_ROOT

RESULTS_ROOT = REPO_ROOT / "eval" / "results"


def git_commit() -> tuple[str, bool]:
    """The short commit hash and whether the working tree has uncommitted changes."""

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()

    return git("rev-parse", "--short", "HEAD"), bool(git("status", "--porcelain"))


def markdown(report: dict[str, Any]) -> str:
    """A readable summary table of every stage in the report."""
    lines = [
        f"# Evaluation: {report['split']} split",
        "",
        f"- Date: {report['date']}",
        f"- Commit: `{report['commit']}`" + (" (uncommitted changes)" if report["dirty"] else ""),
        "- Datasets: " + ", ".join(f"`{d['dataset_id']}`" for d in report["datasets"]),
        "- Settings: recorded in metrics.json",
        "",
    ]
    joins = report.get("joins")
    if joins:
        lines += [
            "## Join discovery",
            "",
            "| System | Precision | Recall | F1 | Undirected F1 | Normalization recall "
            "| Fan-out recall | Fan-out precision | Decoy rejection |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for system, result in joins.items():
            m = result["aggregate"]
            cells = [
                m["precision"],
                m["recall"],
                m["f1"],
                m["undirected_f1"],
                m["normalization_recall"],
                m["fan_out_recall"],
                m["fan_out_precision"],
                m["decoy_rejection"],
            ]
            shown = " | ".join("n/a" if c is None else f"{c:.3f}" for c in cells)
            lines.append(f"| {system} | {shown} |")
        lines += ["", "### Errors by system", ""]
        for system, result in joins.items():
            errors = result["false_positives"][:8] + result["false_negatives"][:8]
            fp, fn = len(result["false_positives"]), len(result["false_negatives"])
            lines.append(f"- **{system}**: {fp} false positives, {fn} false negatives")
            lines += [f"  - {e}" for e in errors]
    views = report.get("views")
    if views:
        lines += [
            "",
            "## Views and SIT checks (deterministic agent, no model)",
            "",
            "| Reviewer | Views valid | Checks passed (first try) | Checks passed (final) "
            "| Avg repair attempts | Views repaired |",
            "|---|---|---|---|---|---|",
        ]
        for mode, result in views.items():
            m = result["aggregate"]
            cells = [m["view_validity"], m["check_pass_first"], m["check_pass_final"]]
            shown = " | ".join("n/a" if c is None else f"{c:.3f}" for c in cells)
            lines.append(
                f"| {mode} | {shown} | {m['avg_repair_attempts']} | {m['views_repaired']} |"
            )
    kpis = report.get("kpis")
    if kpis and kpis["aggregate"]["total"]:
        overall = kpis["aggregate"]
        lines += [
            "",
            "## KPI correctness (recommended joins approved)",
            "",
            f"- Values right: {overall['right']} of {overall['total']} "
            f"({overall['kpi_accuracy']:.1%}); counts exact, money within 0.01%",
            "",
            "| Dataset | " + " | ".join(next(iter(kpis["per_dataset"].values()))) + " |",
            "|---|" + "---|" * len(next(iter(kpis["per_dataset"].values()))),
        ]
        for dataset, metrics in kpis["per_dataset"].items():
            cells = " | ".join(f"{m['right']}/{m['total']}" for m in metrics.values())
            lines.append(f"| {dataset} | {cells} |")
            lines += [f"  - wrong: {w}" for m in metrics.values() for w in m["wrong"]]
    redteam = report.get("redteam")
    if redteam:
        lines += [
            "",
            "## SQL safety",
            "",
            f"- Attacks blocked: {redteam['block_rate']:.1%} of {redteam['attacks']}"
            + (f" (missed: {', '.join(redteam['missed'])})" if redteam["missed"] else ""),
            f"- Harmless queries wrongly blocked: {redteam['false_block_rate']:.1%} "
            f"of {redteam['harmless']}",
        ]
    return "\n".join(lines) + "\n"


def write_results(report: dict[str, Any], root: Path = RESULTS_ROOT) -> Path:
    """Write metrics.json and metrics.md to a dated folder and refresh latest-<split>.md."""
    folder = root / f"{report['date'][:10]}-{report['commit']}-{report['split']}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "metrics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    text = markdown(report)
    (folder / "metrics.md").write_text(text, encoding="utf-8")
    (root / f"latest-{report['split']}.md").write_text(text, encoding="utf-8")
    return folder


def new_report(split: str) -> dict[str, Any]:
    """Report skeleton with provenance."""
    commit, dirty = git_commit()
    return {
        "split": split,
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": commit,
        "dirty": dirty,
        "datasets": [],
    }
