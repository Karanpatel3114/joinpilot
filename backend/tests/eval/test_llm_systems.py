from pathlib import Path
from typing import Any

import duckdb
import pytest

import eval.run_all as run_all
from eval.datasets import EvalDataset
from eval.llm_systems import joinpilot_full, llm_only, schema_text
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


def test_full_agent_without_a_model_falls_back_to_the_scorer(sap_profile: ProjectProfile) -> None:
    edges = joinpilot_full(sap_profile, UnavailableProvider("off"), SETTINGS)
    assert len(edges) == 5
    assert any(e.normalization == "lpad_zeros:10" for e in edges)


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
    assert results["joinpilot_full"]["summary"]["recall"]["mean"] == 1.0


def test_spread_reports_mean_and_range() -> None:
    assert run_all.spread([0.5, 1.0, 0.75]) == {"mean": 0.75, "min": 0.5, "max": 1.0}
