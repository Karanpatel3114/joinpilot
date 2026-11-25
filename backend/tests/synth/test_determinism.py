"""The same seed, size and naming must always produce byte-identical output."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from joinpilot.config import IssueRates, SynthSettings
from joinpilot.synth.dataset import build_dataset, fingerprint
from joinpilot.synth.generate import write_dataset
from joinpilot.synth.gold import write_gold

SETTINGS = SynthSettings()


def file_hashes(folder: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}


def test_same_inputs_give_byte_identical_files(tmp_path: Path) -> None:
    for run in ("a", "b"):
        dataset = build_dataset(3, "S", "sap", SETTINGS)
        write_dataset(dataset, tmp_path / run / "data")
        write_gold(dataset, tmp_path / run / "gold", SETTINGS)
    assert file_hashes(tmp_path / "a" / "data") == file_hashes(tmp_path / "b" / "data")
    assert file_hashes(tmp_path / "a" / "gold") == file_hashes(tmp_path / "b" / "gold")


def test_different_seeds_give_different_fingerprints() -> None:
    first = build_dataset(1, "S", "sap", SETTINGS).output_tables()
    second = build_dataset(2, "S", "sap", SETTINGS).output_tables()
    assert fingerprint(first) != fingerprint(second)


def test_naming_mode_changes_names_but_not_rows() -> None:
    sap = build_dataset(1, "S", "sap", SETTINGS)
    friendly = build_dataset(1, "S", "friendly", SETTINGS)
    assert fingerprint(sap.canonical) == fingerprint(friendly.canonical)
    assert fingerprint(sap.output_tables()) != fingerprint(friendly.output_tables())


# Pinned so that a numpy, pyarrow or platform change that alters the data fails CI
# instead of silently invalidating the committed gold. Update only together with gold.
PINNED_FINGERPRINT_S1_SAP = (
    "sha256:c73fd3e7464a8ded4f8f3bb647b9320a9311cfdd23f7313d71318fe218405a17"
)


def test_dev_dataset_fingerprint_is_pinned() -> None:
    dataset = build_dataset(1, "S", "sap", SynthSettings())
    assert fingerprint(dataset.output_tables()) == PINNED_FINGERPRINT_S1_SAP


def test_gold_manifest_records_fingerprint_version_and_settings(tmp_path: Path) -> None:
    dataset = build_dataset(2, "S", "friendly", SETTINGS)
    write_gold(dataset, tmp_path, SETTINGS)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["fingerprint"] == fingerprint(dataset.output_tables())
    assert manifest["generator_version"] == "1"
    assert manifest["settings"]["issues"]["orphan_order_items"] == 0.01


def test_issue_rates_outside_zero_to_one_are_rejected() -> None:
    with pytest.raises(ValidationError):
        IssueRates(orphan_order_items=1.5)
    with pytest.raises(ValidationError):
        IssueRates(duplicate_customers=0.9)
