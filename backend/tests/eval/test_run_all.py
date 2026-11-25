from pathlib import Path

import duckdb

from eval.datasets import EvalDataset
from eval.run_all import JOIN_SYSTEMS, evaluate_joins, joinpilot_deterministic
from joinpilot.config import SynthSettings
from joinpilot.profiling.models import ProjectProfile
from joinpilot.synth.dataset import build_dataset
from joinpilot.synth.gold import write_gold


def test_deterministic_system_returns_accepted_joins_with_filters(
    sap_profile: ProjectProfile,
) -> None:
    edges = {(e.from_, e.to): e for e in joinpilot_deterministic(sap_profile)}
    assert len(edges) == 5
    assert edges[("MAKT.MATNR", "MARA.MATNR")].filter == ("MAKT.SPRAS", "E")


def test_every_system_is_scored_against_generated_gold(
    sap_profile: ProjectProfile, tmp_path: Path
) -> None:
    write_gold(
        build_dataset(1, "S", "sap", SynthSettings()), tmp_path / "erp_s1_sap", SynthSettings()
    )
    dataset = EvalDataset("erp_s1_sap", "sha256:x", duckdb.connect(), sap_profile, 0.1)
    results = evaluate_joins([dataset], gold_root=tmp_path)
    assert set(results) == set(JOIN_SYSTEMS)
    deterministic = results["joinpilot_deterministic"]["aggregate"]
    assert (deterministic["f1"], deterministic["normalization_recall"]) == (1.0, 1.0)
    assert results["name_only"]["aggregate"]["normalization_recall"] == 0.0
    assert results["inclusion_dependency"]["aggregate"]["fan_out_recall"] == 0.0
