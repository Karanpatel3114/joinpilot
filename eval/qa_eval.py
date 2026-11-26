"""Question answering: execution accuracy against the generator's answers.

Each dataset's model is built by the real graph with the recommended joins approved
and the gold reference date; every gold question then goes through
`qa.answer.answer_question`, the path the API uses. An answer is right when its rows
equal the gold rows (docs/eval-plan.md): as a multiset unless the question asks for
an order, with numbers compared at two decimals, digit-only ids without leading
zeros, and answer columns matched to gold columns by their values (names and extra
columns are free, which can let a one-row answer match by coincidence). Needs a language
model, so it runs only with `--llm`; failures of that model count as blocked answers.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import nullcontext
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from itertools import product
from pathlib import Path
from typing import Any

import duckdb

from eval.datasets import EvalDataset
from eval.gold import GOLD_ROOT, load_kpis, load_questions
from eval.views_eval import rate, run_graph
from joinpilot.config import Settings
from joinpilot.llm.factory import UnavailableProvider, make_base_provider
from joinpilot.llm.provider import LLMProvider
from joinpilot.qa.answer import OpenWarehouse, answer_question

CENT = Decimal("0.01")


def skip_reason(settings: Settings) -> str | None:
    """Why question answering cannot be evaluated at all (no model configured), if so.

    Only a missing model skips the evaluation; a model that fails or replies badly on
    some questions is part of what is measured, as blocked answers.
    """
    base = make_base_provider(settings)
    if isinstance(base, UnavailableProvider):
        return base.reason
    return None


def shared(con: duckdb.DuckDBPyConnection) -> OpenWarehouse:
    """The evaluation's in-memory warehouse, handed out without closing it."""
    return lambda: nullcontext(con)


def normalize(value: Any) -> Any:
    """Numbers (and numeric text, such as padded ids) to two decimals; text trimmed."""
    if value is None or isinstance(value, bool):
        return value
    try:
        return Decimal(str(value).strip()).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return str(value).strip()


def rows_match(
    gold_rows: list[list[Any]], columns: list[str], rows: list[dict[str, Any]], ordered: bool
) -> bool:
    """True when some choice of answer columns reproduces the gold rows exactly."""
    if len(rows) != len(gold_rows) or not gold_rows:
        return len(rows) == len(gold_rows)
    gold = [[normalize(v) for v in row] for row in gold_rows]
    answer = {c: [normalize(r.get(c)) for r in rows] for c in columns}
    width = len(gold[0])
    candidates = [
        [c for c in columns if Counter(answer[c]) == Counter(row[j] for row in gold)]
        for j in range(width)
    ]
    expected = [tuple(row) for row in gold]
    for choice in product(*candidates):
        if len(set(choice)) < width:
            continue
        got = list(zip(*(answer[c] for c in choice), strict=True))
        if (got == expected) if ordered else (Counter(got) == Counter(expected)):
            return True
    return False


def evaluate_qa(
    datasets: list[EvalDataset],
    settings: Settings,
    llm: LLMProvider,
    gold_root: Path = GOLD_ROOT,
) -> dict[str, Any]:
    """Execution accuracy overall, per tag and per template, with blocked reasons."""
    per_dataset: dict[str, Any] = {}
    by_tag: dict[str, list[bool]] = defaultdict(list)
    by_template: dict[str, list[bool]] = defaultdict(list)
    blocked: Counter[str] = Counter()
    attempts: list[int] = []
    for dataset in datasets:
        questions = load_questions(dataset.dataset_id, gold_root)
        if questions is None:
            continue
        kpis = load_kpis(dataset.dataset_id, gold_root) or {}
        as_of = date.fromisoformat(kpis.get("reference_date", "2026-06-30"))
        settings = settings.model_copy(
            update={"kpi": settings.kpi.model_copy(update={"reference_date": as_of})}
        )
        final = run_graph(dataset, "approve_all", settings, gold_root)
        right, wrong = 0, []
        for q in questions:
            answer = answer_question(
                q["question"],
                run_id=dataset.dataset_id,
                views=final.get("views", []),
                metrics=final.get("metrics", []),
                profile=dataset.profile,
                open_warehouse=shared(dataset.con),
                llm=llm,
                settings=settings,
            )
            ok = not answer.blocked and rows_match(
                q["rows"], answer.columns, answer.rows, q["ordered"]
            )
            if answer.blocked:
                blocked[answer.reason_code or "UNKNOWN"] += 1
            if answer.evidence:
                attempts.append(answer.evidence.attempts)
            right += ok
            by_template[q["template"]].append(ok)
            for tag in q["tags"] or ["none"]:
                by_tag[tag].append(ok)
            if not ok:
                wrong.append({"id": q["id"], "question": q["question"], "sql": answer.sql})
        per_dataset[dataset.dataset_id] = {
            "accuracy": rate(right, len(questions)),
            "right": right,
            "total": len(questions),
            "wrong": wrong[:10],
        }
    right = sum(d["right"] for d in per_dataset.values())
    total = sum(d["total"] for d in per_dataset.values())
    return {
        "aggregate": {
            "execution_accuracy": rate(right, total),
            "right": right,
            "total": total,
            "blocked": dict(blocked),
            "avg_attempts": round(sum(attempts) / len(attempts), 3) if attempts else None,
        },
        "by_tag": {t: rate(sum(v), len(v)) for t, v in sorted(by_tag.items())},
        "by_template": {t: rate(sum(v), len(v)) for t, v in sorted(by_template.items())},
        "per_dataset": per_dataset,
    }
