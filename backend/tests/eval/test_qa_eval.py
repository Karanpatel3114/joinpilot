from pathlib import Path
from typing import Any

import duckdb
import pytest

from eval.datasets import EvalDataset
from eval.qa_eval import evaluate_qa, rows_match
from joinpilot.config import LLMSettings, ProfilingSettings, Settings, SynthSettings
from joinpilot.errors import LLMUnavailableError
from joinpilot.llm.fake import FakeProvider
from joinpilot.llm.provider import Prompt
from joinpilot.profiling.loader import load_arrow
from joinpilot.profiling.service import profile_project
from joinpilot.synth.dataset import build_dataset
from joinpilot.synth.gold import write_gold


def test_rows_match_by_values_not_names() -> None:
    gold = [["0000100001", "12.50"], ["0000100002", "7.00"]]
    rows = [
        {"total": 7.0, "id": "100002", "extra": "x"},
        {"total": 12.5, "id": "100001", "extra": "y"},
    ]
    assert rows_match(gold, ["total", "id", "extra"], rows, ordered=False)
    assert not rows_match(gold, ["total", "id", "extra"], rows, ordered=True)
    assert rows_match(gold, ["total", "id", "extra"], list(reversed(rows)), ordered=True)


def test_rows_must_be_exact_to_the_cent_and_complete() -> None:
    assert rows_match([["10.00"]], ["n"], [{"n": 9.999}], ordered=False)
    assert not rows_match([["10.00"]], ["n"], [{"n": 10.01}], ordered=False)
    assert not rows_match([["1"], ["2"]], ["n"], [{"n": 1}], ordered=False)
    assert not rows_match([["a", "b"]], ["x"], [{"x": "a"}], ordered=False)
    assert rows_match([], ["n"], [], ordered=False)


def dataset_with_gold(tmp_path: Path) -> EvalDataset:
    dataset = build_dataset(1, "S", "sap", SynthSettings())
    write_gold(dataset, tmp_path / dataset.dataset_id, SynthSettings())
    con = duckdb.connect()
    tables = dataset.output_tables()
    for name, data in tables.items():
        load_arrow(con, name, data)
    profile = profile_project(con, {n: n for n in tables}, ProfilingSettings())
    return EvalDataset(dataset.dataset_id, "sha256:x", con, profile, 0.1)


def test_questions_run_through_the_shared_answer_path(tmp_path: Path) -> None:
    def answer(prompt: Prompt) -> dict[str, Any]:
        if "total amount of all open receivables" in prompt.user:
            sql = 'SELECT ROUND(SUM("DMBTR"), 2) AS open_amount FROM model."v_bsid"'
        else:
            sql = 'SELECT -987654 AS wrong FROM "KNA1" LIMIT 1'
        return {"sql": sql, "chart": "number", "explanation": "x"}

    settings = Settings(_env_file=None, llm=LLMSettings(provider="fake"))
    result = evaluate_qa(
        [dataset_with_gold(tmp_path)], settings, FakeProvider({"qa_sql": answer}), tmp_path
    )
    assert result["by_template"]["open_total"] == 1.0
    assert result["aggregate"]["right"] == 1 and result["aggregate"]["total"] >= 30
    assert result["aggregate"]["blocked"] == {} and result["aggregate"]["avg_attempts"] == 1.0
    assert result["by_tag"]["orphans"] is not None


def test_without_a_model_the_evaluation_is_skipped(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, llm=LLMSettings(provider="fake"))
    with pytest.raises(LLMUnavailableError):
        evaluate_qa([dataset_with_gold(tmp_path)], settings, FakeProvider(), tmp_path)
