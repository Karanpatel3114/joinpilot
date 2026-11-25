import json
from pathlib import Path

import pytest

import eval.datasets as datasets
from joinpilot.config import ProfilingSettings


def test_dev_dataset_is_regenerated_and_matches_its_gold() -> None:
    loaded = datasets.load_dataset("erp_s1_sap", ProfilingSettings())
    assert loaded.fingerprint.startswith("sha256:")
    assert {t.name for t in loaded.profile.tables} == {
        "KNA1",
        "MARA",
        "MAKT",
        "VBAK",
        "VBAP",
        "BSID",
    }
    loaded.con.close()


def test_a_fingerprint_mismatch_refuses_to_evaluate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    folder = tmp_path / "erp_s1_sap"
    folder.mkdir()
    (folder / "manifest.json").write_text(json.dumps({"fingerprint": "sha256:stale"}))
    monkeypatch.setattr(
        datasets,
        "load_manifest",
        lambda i: json.loads((tmp_path / i / "manifest.json").read_text()),
    )
    with pytest.raises(datasets.GoldMismatchError):
        datasets.load_dataset("erp_s1_sap", ProfilingSettings())


def test_dev_split_ids_and_test_split_includes_tpch() -> None:
    assert datasets.split_ids("dev") == [
        "erp_s1_sap",
        "erp_s2_sap",
        "erp_s3_sap",
        "erp_s1_friendly",
    ]
    assert datasets.split_ids("test")[-1] == "tpch_sf0.1"


def test_missing_gold_manifest_refuses_to_evaluate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(datasets, "load_manifest", lambda dataset_id: None)
    with pytest.raises(datasets.GoldMismatchError, match="no manifest"):
        datasets.load_dataset("erp_s1_sap", ProfilingSettings())
