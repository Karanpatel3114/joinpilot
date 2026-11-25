import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from eval.gold import load_joins, load_manifest
from joinpilot.config import SynthSettings
from joinpilot.synth.dataset import build_dataset
from joinpilot.synth.gold import write_gold
from joinpilot.synth.tpch import tpch_gold


def test_generated_gold_parses_strictly(tmp_path: Path) -> None:
    dataset = build_dataset(2, "S", "sap", SynthSettings())
    write_gold(dataset, tmp_path / dataset.dataset_id, SynthSettings())
    gold = load_joins(dataset.dataset_id, tmp_path)
    assert len(gold.edges) == 5 and len(gold.decoys) == 5
    manifest = load_manifest(dataset.dataset_id, tmp_path)
    assert manifest is not None and manifest["fingerprint"].startswith("sha256:")


def test_tpch_gold_keeps_its_composite_edge(tmp_path: Path) -> None:
    folder = tmp_path / "tpch_sf0.1"
    folder.mkdir()
    (folder / "joins.json").write_text(json.dumps(tpch_gold(0.1)))
    gold = load_joins("tpch_sf0.1", tmp_path)
    assert gold.composite_edges[0].label == (
        "lineitem.l_partkey+lineitem.l_suppkey",
        "partsupp.ps_partkey+partsupp.ps_suppkey",
    )
    assert load_manifest("tpch_sf0.1", tmp_path) is None


def test_unknown_gold_fields_are_rejected(tmp_path: Path) -> None:
    folder = tmp_path / "x"
    folder.mkdir()
    (folder / "joins.json").write_text(json.dumps({"dataset_id": "x", "edges": [], "surprise": 1}))
    with pytest.raises(ValidationError):
        load_joins("x", tmp_path)
