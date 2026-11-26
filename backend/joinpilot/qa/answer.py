"""The one path from a question to an answer, shared by the API, the MCP server and the
evaluation, so reported accuracy comes from the code that runs.

The warehouse is opened twice and briefly: once to describe the model and build the
guard's catalog, once to run the guarded query. The language model is called in
between, with no lock held.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any, Literal, cast

import duckdb
from pydantic import BaseModel, ValidationError

from joinpilot.config import Settings
from joinpilot.errors import JoinPilotError, LLMUnavailableError
from joinpilot.llm.provider import LLMProvider
from joinpilot.profiling.models import ProjectProfile
from joinpilot.qa.execute import run_query
from joinpilot.qa.generate import Chart, draft_sql
from joinpilot.qa.semantic import describe_columns, model_columns, render_model
from joinpilot.sqlgen.guard import SANDBOX_SCHEMA, UnsafeSQLError, catalog_from_connection

logger = logging.getLogger(__name__)

ReasonCode = Literal[
    "UNSAFE_SQL", "UNKNOWN_IDENTIFIER", "TIMEOUT", "LLM_UNAVAILABLE", "QUERY_FAILED"
]
REASONS = frozenset(
    {"UNSAFE_SQL", "UNKNOWN_IDENTIFIER", "TIMEOUT", "LLM_UNAVAILABLE", "QUERY_FAILED"}
)
OpenWarehouse = Callable[[], AbstractContextManager[duckdb.DuckDBPyConnection]]


class Evidence(BaseModel):
    """Where an answer came from and how it was produced."""

    run_id: str
    views: list[str]
    explanation: str
    attempts: int
    row_count: int
    truncated: bool
    elapsed_ms: float


class Answer(BaseModel):
    """A question's answer: the SQL, the rows and the evidence, or why it was blocked."""

    question: str
    sql: str | None
    columns: list[str]
    rows: list[dict[str, Any]]
    chart: Chart
    evidence: Evidence | None
    blocked: bool
    reason_code: ReasonCode | None
    message: str | None


def answer_question(
    question: str,
    *,
    run_id: str,
    views: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    profile: ProjectProfile,
    open_warehouse: OpenWarehouse,
    llm: LLMProvider,
    settings: Settings,
) -> Answer:
    """Draft guarded SQL for a question over a run's model and run it read-only."""
    qa = settings.qa
    facts = {v["name"]: v["fact_table"] for v in views if v["status"] != "failed"}
    with open_warehouse() as con:
        columns = model_columns(con, set(facts))
        catalog = catalog_from_connection(con, (SANDBOX_SCHEMA, "main"))
    model = render_model(describe_columns(columns, facts, profile, settings.kpi, qa.example_values))
    examples = "\n\n".join(
        f"-- {m['title']}\n{m['sql']}" for m in metrics if m.get("status") == "computed"
    )
    try:
        drafted = draft_sql(question, model, examples, llm, catalog, qa.max_attempts)
    except (LLMUnavailableError, UnsafeSQLError) as error:
        return blocked(question, error)
    except ValidationError:
        return blocked(question, LLMUnavailableError("The model's reply was not valid."))
    try:
        with open_warehouse() as con:
            result = run_query(con, drafted.sql, qa.row_limit, qa.timeout_seconds)
    except JoinPilotError as error:
        return blocked(question, error, drafted.sql)
    used = sorted(v for v in facts if f'"{v}"' in drafted.sql or f".{v}" in drafted.sql)
    logger.info(
        "question answered on run %s: %d rows in %.0f ms after %d attempt(s)",
        run_id,
        len(result.rows),
        result.elapsed_ms,
        drafted.attempts,
    )
    return Answer(
        question=question,
        sql=drafted.sql,
        columns=result.columns,
        rows=result.rows,
        chart=drafted.chart,
        evidence=Evidence(
            run_id=run_id,
            views=used,
            explanation=drafted.explanation,
            attempts=drafted.attempts,
            row_count=len(result.rows),
            truncated=result.truncated,
            elapsed_ms=result.elapsed_ms,
        ),
        blocked=False,
        reason_code=None,
        message=None,
    )


def blocked(question: str, error: JoinPilotError, sql: str | None = None) -> Answer:
    """An answer that stops with a reason code and a plain message."""
    code = cast(ReasonCode, error.code if error.code in REASONS else "QUERY_FAILED")
    logger.info("question blocked: %s", code)
    return Answer(
        question=question,
        sql=sql,
        columns=[],
        rows=[],
        chart="table",
        evidence=None,
        blocked=True,
        reason_code=code,
        message=error.message,
    )
