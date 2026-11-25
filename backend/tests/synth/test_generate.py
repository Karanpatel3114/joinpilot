import json
from pathlib import Path

import pyarrow.parquet as pq

from joinpilot.config import SynthSettings
from joinpilot.synth.dataset import build_dataset, make_dataset_id
from joinpilot.synth.generate import main, write_dataset


def test_dataset_id_encodes_size_seed_and_naming() -> None:
    assert make_dataset_id(1, "S", "sap") == "erp_s1_sap"
    assert make_dataset_id(101, "M", "friendly") == "erp_m101_friendly"


def test_write_dataset_writes_parquet_files_and_manifest(tmp_path: Path) -> None:
    dataset = build_dataset(1, "S", "sap", SynthSettings())
    manifest = write_dataset(dataset, tmp_path)
    assert sorted(p.name for p in tmp_path.glob("*.parquet")) == [
        "BSID.parquet", "KNA1.parquet", "MAKT.parquet", "MARA.parquet", "VBAK.parquet",
        "VBAP.parquet",
    ]  # fmt: skip
    saved = json.loads((tmp_path / "manifest.json").read_text())
    assert saved == manifest
    assert saved["tables"]["KNA1"]["rows"] == 1_000
    assert str(saved["fingerprint"]).startswith("sha256:")
    assert pq.read_table(tmp_path / "BSID.parquet").column_names[1] == "KUNNR"


def test_cli_writes_data_and_gold(tmp_path: Path) -> None:
    main(["--seed", "2", "--size", "S", "--naming", "friendly",
          "--out", str(tmp_path / "out"), "--gold", str(tmp_path / "gold")])  # fmt: skip
    assert (tmp_path / "out" / "customers.parquet").exists()
    assert (tmp_path / "gold" / "erp_s2_friendly" / "kpis.json").exists()
