from typing import Any

import pytest

from joinpilot.errors import LLMUnavailableError
from joinpilot.llm.fake import FakeProvider
from joinpilot.llm.provider import Prompt
from joinpilot.qa.generate import draft_sql
from joinpilot.sqlgen.guard import SANDBOX_SCHEMA, UnsafeSQLError, catalog_from_connection

GOOD = 'SELECT "aging_bucket", SUM("DMBTR") AS amount FROM model."v_bsid" GROUP BY 1'


def answer(sql: str, chart: str = "bar") -> dict[str, Any]:
    return {"sql": sql, "chart": chart, "explanation": "Sums open amounts per bucket."}


def ask(model: Any, llm: FakeProvider, attempts: int = 2) -> Any:
    con = model[0]
    catalog = catalog_from_connection(con, (SANDBOX_SCHEMA,))
    return draft_sql(
        "Open amount by aging bucket?", "MODEL TEXT", "EXAMPLES", llm, catalog, attempts
    )


def test_a_guarded_draft_comes_back_with_its_chart(model: Any) -> None:
    llm = FakeProvider({"qa_sql": lambda _: answer(GOOD)})
    drafted = ask(model, llm)
    assert drafted.attempts == 1 and drafted.chart == "bar"
    assert '"v_bsid"' in drafted.sql
    prompt = llm.calls[0]
    assert "Open amount by aging bucket?" in prompt.user and "MODEL TEXT" in prompt.user
    assert "EXAMPLES" in prompt.user


def test_a_refused_draft_gets_one_fix_with_the_reason(model: Any) -> None:
    replies = iter([answer("SELECT * FROM BSID"), answer(GOOD)])
    llm = FakeProvider({"qa_sql": lambda _: next(replies)})
    drafted = ask(model, llm)
    assert drafted.attempts == 2
    fix: Prompt = llm.calls[1]
    assert "was refused before it ran" in fix.user and "SELECT * FROM BSID" in fix.user


def test_sql_that_never_passes_the_guard_is_not_returned(model: Any) -> None:
    llm = FakeProvider({"qa_sql": lambda _: answer("DROP VIEW model.v_bsid")})
    with pytest.raises(UnsafeSQLError):
        ask(model, llm)
    assert len(llm.calls) == 2


def test_no_model_means_no_answer(model: Any) -> None:
    with pytest.raises(LLMUnavailableError):
        ask(model, FakeProvider())
