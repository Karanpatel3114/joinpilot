"""Answer plain-English questions over a project's newest tested model.

The service finds the model (the most recently completed run's views and metrics)
and the project's warehouse, then hands over to `joinpilot.qa.answer`, the one path
the API, the MCP server and the evaluation share. It also records model usage.
"""

from __future__ import annotations

from functools import partial

from joinpilot.config import Settings
from joinpilot.db.models import LLMCallRow
from joinpilot.db.session import session_scope
from joinpilot.errors import ConflictError, InvalidInputError
from joinpilot.llm.factory import make_provider
from joinpilot.llm.observed import UsageLog
from joinpilot.qa.answer import Answer, Evidence, answer_question
from joinpilot.services.projects import ProjectService
from joinpilot.services.runs import RunService

__all__ = ["Answer", "Evidence", "QuestionService"]


class QuestionService:
    """Questions for the API and the MCP server."""

    def __init__(self, settings: Settings, runs: RunService) -> None:
        self.settings = settings
        self.runs = runs
        self.projects = ProjectService(settings)

    def ask(self, project_id: str, question: str) -> Answer:
        """Answer a question over the project's most recently completed model."""
        limit = self.settings.qa.max_question_chars
        question = question.strip()
        if not 3 <= len(question) <= limit:
            raise InvalidInputError(
                "Ask a question between 3 and the allowed number of characters.",
                {"max_question_chars": limit},
            )
        run_id, metrics = self.runs.dashboard(project_id)
        if conflict := self.runs.model_conflict(project_id):
            raise ConflictError(conflict)
        views = [v for v in self.runs.views(run_id) if v["status"] != "failed"] if run_id else []
        if run_id is None or not views:
            raise ConflictError("Build and approve a data model before asking questions.")
        log = UsageLog()
        try:
            return answer_question(
                question,
                run_id=run_id,
                views=views,
                metrics=metrics,
                profile=self.projects.profile(project_id),
                open_warehouse=partial(self.projects.read_only_warehouse, project_id),
                llm=make_provider(self.settings, log),
                settings=self.settings,
            )
        finally:
            self._save_usage(run_id, log)

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
