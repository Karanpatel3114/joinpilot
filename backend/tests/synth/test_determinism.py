"""The same seed, size and naming must always produce byte-identical output."""

import hashlib
from pathlib import Path

from joinpilot.config import SynthSettings
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
