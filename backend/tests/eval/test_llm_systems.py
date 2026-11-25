from pathlib import Path
from typing import Any

import duckdb
import pytest

import eval.run_all as run_all
from eval.datasets import EvalDataset
from eval.llm_systems import (
    ERP_REQUIREMENT,
    TPCH_REQUIREMENT,
    joinpilot_full,
    llm_only,
    requirement_for,
    schema_text,
)
from joinpilot.config import LLMSettings, Settings, SynthSettings
from joinpilot.llm.factory import UnavailableProvider
from joinpilot.llm.fake import FakeProvider
from joinpilot.llm.provider import Prompt
from joinpilot.profiling.models import ProjectProfile
from joinpilot.synth.dataset import build_dataset
from joinpilot.synth.gold import write_gold

SETTINGS = Settings(_env_file=None)


def schema_model(answer: list[dict[str, str]]) -> FakeProvider:
    return FakeProvider().on("llm_only_joins", lambda p: {"joins": answer})


def test_llm_only_sees_names_and_types_but_no_evidence(sap_profile: ProjectProfile) -> None:
    text = schema_text(sap_profile)
    assert "KNA1: KUNNR VARCHAR" in text
    assert "0000" not in text and "rows" not in text


def test_llm_only_keeps_known_columns_and_drops_inventions(sap_profile: ProjectProfile) -> None:
    fake = schema_model(
        [
            {"from": "vbak.kunnr", "to": "KNA1.KUNNR"},
            {"from": "BSID.KUNNR", "to": "KNA1.CUSTOMER"},
            {"from": "KNA1.KUNNR", "to": "KNA1.KUNNR"},
        ]
    )
    edges = llm_only(sap_profile, fake)
    assert [(e.from_, e.to) for e in edges] == [("VBAK.KUNNR", "KNA1.KUNNR")]


def test_full_agent_reports_when_it_fell_back_to_the_scorer(sap_profile: ProjectProfile) -> None:
    edges, diagnostics = joinpilot_full(
        sap_profile, UnavailableProvider("off"), SETTINGS, ERP_REQUIREMENT
    )
    assert len(edges) == 5
    assert any(e.normalization == "lpad_zeros:10" for e in edges)
    assert diagnostics["parse_source"] == "fallback"
    assert diagnostics["model_used"] is False
    assert diagnostics["model_explained"] == 0 and diagnostics["templated"] > 0


def include_everything(prompt: Prompt) -> dict[str, Any]:
    edge_ids = [line.split(":", 1)[0] for line in prompt.user.splitlines() if line[:1] == "e"]
    return {
        "joins": [
            {"edge_id": e, "include": True, "relevance": "required", "explanation": "See evidence."}
            for e in edge_ids
        ]
    }


def test_llm_runs_report_mean_range_and_usage(
    sap_profile: ProjectProfile, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_gold(
        build_dataset(1, "S", "sap", SynthSettings()), tmp_path / "erp_s1_sap", SynthSettings()
    )
    fake = schema_model([{"from": "VBAK.KUNNR", "to": "KNA1.KUNNR"}]).on(
        "rank_joins", include_everything
    )
    monkeypatch.setattr(run_all, "make_base_provider", lambda settings: fake)
    dataset = EvalDataset("erp_s1_sap", "sha256:x", duckdb.connect(), sap_profile, 0.1)
    settings = Settings(_env_file=None, llm=LLMSettings(provider="fake"))
    results = run_all.evaluate_llm_joins([dataset], settings, runs=2, gold_root=tmp_path)
    only = results["llm_only"]
    assert len(only["runs"]) == 2
    assert only["summary"]["precision"] == {"mean": 1.0, "min": 1.0, "max": 1.0}
    assert only["summary"]["recall"]["mean"] == 0.2
    assert only["runs"][0]["usage"]["calls"] == 1
    full = results["joinpilot_full"]
    assert full["summary"]["recall"]["mean"] == 1.0
    diagnostics = full["runs"][0]["per_dataset"]["erp_s1_sap"]["diagnostics"]
    assert diagnostics["parse_source"] == "fallback"
    assert diagnostics["model_used"] is True


def test_a_failing_llm_only_dataset_counts_as_an_empty_prediction(
    sap_profile: ProjectProfile, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_gold(
        build_dataset(1, "S", "sap", SynthSettings()), tmp_path / "erp_s1_sap", SynthSettings()
    )
    monkeypatch.setattr(run_all, "make_base_provider", lambda settings: FakeProvider())
    dataset = EvalDataset("erp_s1_sap", "sha256:x", duckdb.connect(), sap_profile, 0.1)
    settings = Settings(_env_file=None, llm=LLMSettings(provider="fake"))
    run = run_all.run_llm_system("llm_only", [dataset], settings, tmp_path)
    assert run["aggregate"]["recall"] == 0.0 and run["aggregate"]["gold"] == 5
    assert "failed" in run["per_dataset"]["erp_s1_sap"]["diagnostics"]
    assert run["usage"]["failed_calls"] == 1


def test_each_schema_gets_its_own_requirement() -> None:
    assert requirement_for("tpch_sf0.1") == TPCH_REQUIREMENT
    assert requirement_for("erp_s1_sap") == ERP_REQUIREMENT


def test_spread_reports_mean_and_range_and_skips_undefined_values() -> None:
    assert run_all.spread([0.5, 1.0, 0.75]) == {"mean": 0.75, "min": 0.5, "max": 1.0}
    assert run_all.spread([None, 1.0]) == {"mean": 1.0, "min": 1.0, "max": 1.0}
    assert run_all.spread([None]) is None
