"""Fail CI when the newest evaluation drops below the numbers the README reports.

    uv run python -m eval.run_all --split dev && uv run python -m eval.smoke

Reads the newest `eval/results/*-dev/metrics.json` and checks the headline numbers:
deterministic join F1, view validity and check pass rate, KPI accuracy, and the SQL
red-team block rate with no ordinary query blocked.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

from eval.results import RESULTS_ROOT

logger = logging.getLogger(__name__)

FLOORS: dict[str, float] = {
    "join_f1": 1.0,
    "view_validity": 1.0,
    "check_pass_final": 1.0,
    "kpi_accuracy": 1.0,
    "attack_block_rate": 1.0,
}


def headline(report: dict[str, Any]) -> dict[str, float]:
    """The numbers the README cites, from one results report."""
    views = report["views"]["approve_all"]["aggregate"]
    return {
        "join_f1": report["joins"]["joinpilot_deterministic"]["aggregate"]["f1"],
        "view_validity": views["view_validity"],
        "check_pass_final": views["check_pass_final"],
        "kpi_accuracy": report["kpis"]["aggregate"]["kpi_accuracy"],
        "attack_block_rate": report["redteam"]["block_rate"],
        "harmless_blocked": report["redteam"]["false_block_rate"],
    }


def failures(numbers: dict[str, float]) -> list[str]:
    """Every headline number below its floor, and any ordinary query blocked."""
    problems = [
        f"{name} is {numbers[name]}, below {floor}"
        for name, floor in FLOORS.items()
        if numbers[name] is None or numbers[name] < floor
    ]
    if numbers["harmless_blocked"]:
        problems.append(f"{numbers['harmless_blocked']:.1%} of ordinary queries were blocked")
    return problems


def main(root: Path = RESULTS_ROOT) -> None:
    newest = max(root.glob("*-dev/metrics.json"), key=lambda p: p.stat().st_mtime)
    numbers = headline(json.loads(newest.read_text()))
    logger.info(f"{newest.parent.name}: {json.dumps(numbers)}")
    if problems := failures(numbers):
        logger.info("evaluation smoke test failed:\n- " + "\n- ".join(problems))
        sys.exit(1)
    logger.info("evaluation smoke test passed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
