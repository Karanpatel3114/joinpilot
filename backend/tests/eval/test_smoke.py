import json
from pathlib import Path

import pytest

from eval.smoke import failures, main

GOOD = {
    "join_f1": 1.0,
    "view_validity": 1.0,
    "check_pass_final": 1.0,
    "kpi_accuracy": 1.0,
    "attack_block_rate": 1.0,
    "harmless_blocked": 0.0,
}


def test_every_headline_number_has_a_floor() -> None:
    assert failures(GOOD) == []
    assert failures({**GOOD, "kpi_accuracy": 0.99}) == ["kpi_accuracy is 0.99, below 1.0"]
    assert failures({**GOOD, "view_validity": None}) != []  # type: ignore[dict-item]
    assert failures({**GOOD, "harmless_blocked": 0.09}) == ["9.0% of ordinary queries were blocked"]


def test_the_newest_results_file_decides(tmp_path: Path) -> None:
    report = {
        "joins": {"joinpilot_deterministic": {"aggregate": {"f1": 0.9}}},
        "views": {"approve_all": {"aggregate": {"view_validity": 1.0, "check_pass_final": 1.0}}},
        "kpis": {"aggregate": {"kpi_accuracy": 1.0}},
        "redteam": {"block_rate": 1.0, "false_block_rate": 0.0},
    }
    (tmp_path / "2026-11-26-abc-dev").mkdir()
    (tmp_path / "2026-11-26-abc-dev" / "metrics.json").write_text(json.dumps(report))
    with pytest.raises(SystemExit):
        main(tmp_path)
