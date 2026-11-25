import json
from pathlib import Path

from eval.results import git_commit, markdown, new_report, write_results


def sample_report() -> dict[str, object]:
    report = new_report("dev")
    report["datasets"] = [{"dataset_id": "erp_s1_sap", "fingerprint": "sha256:x"}]
    metrics = {"precision": 1.0, "recall": 0.5, "f1": 0.6667, "normalization_accuracy": None,
               "fan_out_recall": 1.0, "decoy_rejection": 0.75}  # fmt: skip
    report["joins"] = {"name_only": {"aggregate": metrics, "false_positives": ["a -> b"],
                                     "false_negatives": []}}  # fmt: skip
    return report


def test_report_records_commit_date_and_split() -> None:
    report = new_report("dev")
    commit, _ = git_commit()
    assert report["commit"] == commit and len(commit) >= 7
    assert report["split"] == "dev"
    assert str(report["date"]).endswith("+00:00")


def test_results_are_written_to_a_dated_folder_and_latest(tmp_path: Path) -> None:
    report = sample_report()
    folder = write_results(report, root=tmp_path)
    assert folder.name == f"{str(report['date'])[:10]}-{report['commit']}-dev"
    assert json.loads((folder / "metrics.json").read_text())["split"] == "dev"
    latest = (tmp_path / "latest-dev.md").read_text()
    assert latest == (folder / "metrics.md").read_text()
    assert "| name_only | 1.000 | 0.500 | 0.667 | n/a | 1.000 | 0.750 |" in latest


def test_markdown_lists_errors_per_system() -> None:
    text = markdown(sample_report())
    assert "**name_only**: 1 false positives, 0 false negatives" in text
    assert "  - a -> b" in text
