"""Answer plain-English questions over a project's newest tested model.

The flow keeps the warehouse lock short: describe the model's views (read-only),
ask the language model for SQL with no lock held, then run the guarded query
read-only with a row limit and a timeout. Anything that stops an answer comes back
as a blocked answer with a reason code, never as unguarded SQL.
"""

from __future__ import annotations

import logging
from typing import Any, Literal, cast

from pydantic import BaseModel, ValidationError

from joinpilot.config import Settings
from joinpilot.db.models import LLMCallRow
from joinpilot.db.session import session_scope
from joinpilot.errors import ConflictError, InvalidInputError, JoinPilotError, LLMUnavailableError
from joinpilot.llm.factory import make_provider
from joinpilot.llm.observed import UsageLog
from joinpilot.qa.execute import run_query
from joinpilot.qa.generate import Chart, draft_sql
from joinpilot.qa.semantic import describe_columns, model_columns, render_model
from joinpilot.services.projects import ProjectService
from joinpilot.services.runs import RunService
from joinpilot.sqlgen.guard import SANDBOX_SCHEMA, UnsafeSQLError, catalog_from_connection

logger = logging.getLogger(__name__)

ReasonCode = Literal[
    "UNSAFE_SQL", "UNKNOWN_IDENTIFIER", "TIMEOUT", "LLM_UNAVAILABLE", "QUERY_FAILED"
]


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


class QuestionService:
    """The one place questions are answered, for the API, the MCP server and the eval."""

    def __init__(self, settings: Settings, runs: RunService) -> None:
        self.settings = settings
        self.runs = runs
        self.projects = ProjectService(settings)

    def ask(self, project_id: str, question: str) -> Answer:
        """Answer a question over the project's most recently completed model."""
        qa = self.settings.qa
        question = question.strip()
        if not 3 <= len(question) <= qa.max_question_chars:
            raise InvalidInputError(
                "Ask a question between 3 and the allowed number of characters.",
                {"max_question_chars": qa.max_question_chars},
            )
        run_id, metrics = self.runs.dashboard(project_id)
        views = [v for v in self.runs.views(run_id) if v["status"] != "failed"] if run_id else []
        if run_id is None or not views:
            raise ConflictError("Build and approve a data model before asking questions.")
        facts = {v["name"]: v["fact_table"] for v in views}
        with self.projects.read_only_warehouse(project_id) as con:
            columns = [c for c in model_columns(con) if c[0] in facts]
            catalog = catalog_from_connection(con, (SANDBOX_SCHEMA,))
        model = render_model(
            describe_columns(
                columns,
                facts,
                self.projects.profile(project_id),
                self.settings.kpi,
                qa.example_values,
            )
        )
        examples = "\n\n".join(
            f"-- {m['title']}\n{m['sql']}" for m in metrics if m.get("status") == "computed"
        )
        log = UsageLog()
        try:
            drafted = draft_sql(
                question,
                model,
                examples,
                make_provider(self.settings, log),
                catalog,
                qa.max_attempts,
            )
        except (LLMUnavailableError, UnsafeSQLError) as error:
            return blocked(question, error)
        except ValidationError:
            return blocked(question, LLMUnavailableError("The model's reply was not valid."))
        finally:
            self._save_usage(run_id, log)
        try:
            with self.projects.read_only_warehouse(project_id) as con:
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

    def _save_usage(self, run_id: str, log: UsageLog) -> None:
        """Record the model calls a question made against the run whose model it used."""
        records, log.records = log.records, []
        if not records:
            return
        with session_scope(self.settings.db_url) as session:
            session.add_all(
                LLMCallRow(
                    run_id=run_id,
                    purpose=u.purpose,
                    provider=u.provider,
                    model=u.model,
                    input_tokens=u.input_tokens,
                    output_tokens=u.output_tokens,
                    latency_ms=u.latency_ms,
                    cost_usd=u.cost_usd,
                    attempts=u.attempts,
                    cached=u.cached,
                )
                for u in records
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


REASONS = frozenset(
    {"UNSAFE_SQL", "UNKNOWN_IDENTIFIER", "TIMEOUT", "LLM_UNAVAILABLE", "QUERY_FAILED"}
)
