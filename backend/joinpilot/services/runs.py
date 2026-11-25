"""Agent runs: start one, follow its status, read proposals, approve, resume.

The graph's state lives in the checkpointer; this service mirrors what people and
the console need (status, proposals, decisions, warnings, timings, usage) into
the application database after every step.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from langgraph.types import Command
from pydantic import BaseModel
from sqlalchemy import select

from joinpilot.agent.approval import Decision
from joinpilot.agent.checkpoints import open_checkpointer
from joinpilot.agent.graph import AgentContext, build_graph
from joinpilot.config import Settings
from joinpilot.db.models import LLMCallRow, ProposalRow, RunRow
from joinpilot.db.session import ensure_migrated, session_scope
from joinpilot.errors import ConflictError, InvalidInputError, NotFoundError
from joinpilot.jobs.queue import JobQueue
from joinpilot.llm.factory import make_provider
from joinpilot.llm.observed import UsageLog
from joinpilot.services.projects import ProjectService

logger = logging.getLogger(__name__)


class RunRecord(BaseModel):
    """What the API returns for a run."""

    run_id: str
    project_id: str
    status: str
    requirement: str
    parsed_requirement: dict[str, Any] | None
    error: str | None
    warnings: list[str]
    timings_ms: dict[str, float]
    created_at: datetime
    updated_at: datetime


def to_record(row: RunRow) -> RunRecord:
    """Map a run row to its record (times always timezone-aware)."""

    def aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    return RunRecord(
        run_id=row.id,
        project_id=row.project_id,
        status=row.status,
        requirement=row.requirement,
        parsed_requirement=row.parsed_requirement,
        error=row.error,
        warnings=list(row.warnings),
        timings_ms=dict(row.timings_ms),
        created_at=aware(row.created_at),
        updated_at=aware(row.updated_at),
    )


def thread(run_id: str) -> Any:
    """LangGraph config: one checkpoint thread per run."""
    return {"configurable": {"thread_id": run_id}}


class RunService:
    """Every run operation the API, the worker and the MCP server need."""

    def __init__(self, settings: Settings, jobs: JobQueue) -> None:
        self.settings = settings
        self.jobs = jobs
        self.projects = ProjectService(settings)
        ensure_migrated(settings.db_url)

    def start(self, project_id: str, requirement: str) -> RunRecord:
        """Create a run for a project with tables, and queue its first job."""
        project = self.projects.get(project_id)
        if not project.tables:
            raise ConflictError("Load at least one table before starting a run.")
        run_id = str(uuid.uuid4())
        with session_scope(self.settings.db_url) as session:
            session.add(
                RunRow(id=run_id, project_id=project.id, requirement=requirement, status="queued")
            )
        self.jobs.submit("start_run", run_id)
        return self.get(run_id)

    def get(self, run_id: str) -> RunRecord:
        """One run, or NotFoundError."""
        with session_scope(self.settings.db_url) as session:
            return to_record(self._row(session, run_id))

    def list_for_project(self, project_id: str) -> list[RunRecord]:
        """A project's runs, newest first."""
        self.projects.get(project_id)
        query = (
            select(RunRow).where(RunRow.project_id == project_id).order_by(RunRow.created_at.desc())
        )
        with session_scope(self.settings.db_url) as session:
            return [to_record(r) for r in session.scalars(query)]

    def proposals(self, run_id: str) -> list[dict[str, Any]]:
        """The run's proposals with their current status and decision."""
        with session_scope(self.settings.db_url) as session:
            row = self._row(session, run_id)
            return [
                {**p.payload, "status": p.status, "decision_reason": p.decision_reason}
                for p in row.proposals
            ]

    def approve(self, run_id: str, decisions: list[Decision]) -> RunRecord:
        """Record decisions on a paused run and queue the resume."""
        if not decisions:
            raise InvalidInputError("Send at least one decision.")
        with session_scope(self.settings.db_url) as session:
            row = self._row(session, run_id)
            if row.status != "awaiting_approval":
                raise ConflictError("This run is not waiting for approval.", {"status": row.status})
            known = {p.edge_id: p for p in row.proposals}
            unknown = sorted({d.edge_id for d in decisions} - set(known))
            if unknown:
                raise InvalidInputError("Some decisions name unknown joins.", {"edge_ids": unknown})
            now = datetime.now(UTC)
            for d in decisions:
                proposal = known[d.edge_id]
                proposal.status = "approved" if d.action == "approve" else "rejected"
                proposal.decision_reason, proposal.decided_at = d.reason, now
            row.status = "generating"
        self.jobs.submit("resume_run", run_id)
        return self.get(run_id)

    def execute(self, run_id: str) -> None:
        """Run the graph from the start until the approval pause (job body)."""
        run = self.get(run_id)
        start = {
            "run_id": run.run_id,
            "project_id": run.project_id,
            "requirement": run.requirement,
            "status": "profiling",
        }
        self._drive(run, start)

    def resume(self, run_id: str) -> None:
        """Continue a paused run with the recorded decisions (job body)."""
        run = self.get(run_id)
        decisions = [
            {
                "edge_id": p["edge_id"],
                "action": "approve" if p["status"] == "approved" else "reject",
                "reason": p.get("decision_reason"),
            }
            for p in self.proposals(run_id)
            if p["status"] in ("approved", "rejected")
        ]
        self._drive(run, Command(resume=decisions))

    def _drive(self, run: RunRecord, graph_input: Any) -> None:
        """Stream the graph, mirroring each step into the database; record failures."""
        log = UsageLog()
        ctx = AgentContext(
            load_profile=lambda: self.projects.profile(run.project_id),
            llm=make_provider(self.settings, log),
            settings=self.settings,
        )
        try:
            with open_checkpointer(self.settings) as saver:
                graph = build_graph(ctx, saver)
                for values in self._stream(graph, graph_input, run.run_id):
                    self._mirror(run.run_id, values)
                    self._save_usage(run.run_id, log)
        except Exception as error:
            logger.exception("run %s failed", run.run_id)
            self._fail(run.run_id, str(error))

    @staticmethod
    def _stream(graph: Any, graph_input: Any, run_id: str) -> Iterator[dict[str, Any]]:
        yield from graph.stream(graph_input, thread(run_id), stream_mode="values")

    def _mirror(self, run_id: str, values: dict[str, Any]) -> None:
        """Copy the latest state into the run row and its proposal rows."""
        with session_scope(self.settings.db_url) as session:
            row = self._row(session, run_id)
            if "status" in values:
                row.status = values["status"]
            row.parsed_requirement = values.get("parsed_requirement", row.parsed_requirement)
            row.warnings = list(values.get("warnings", row.warnings))
            row.timings_ms = dict(values.get("timings_ms", row.timings_ms))
            existing = {p.edge_id: p for p in row.proposals}
            for position, proposal in enumerate(values.get("proposals", [])):
                if proposal["edge_id"] in existing:
                    continue
                row.proposals.append(
                    ProposalRow(
                        edge_id=proposal["edge_id"],
                        position=position,
                        payload={k: v for k, v in proposal.items() if k != "status"},
                        status=proposal.get("status", "proposed"),
                    )
                )

    def _save_usage(self, run_id: str, log: UsageLog) -> None:
        """Persist the model calls made so far, once each."""
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

    def _fail(self, run_id: str, message: str) -> None:
        with session_scope(self.settings.db_url) as session:
            row = self._row(session, run_id)
            row.status, row.error = "failed", message[:2000]

    @staticmethod
    def _row(session: Any, run_id: str) -> RunRow:
        try:
            key = str(uuid.UUID(run_id))
        except ValueError as error:
            raise NotFoundError("Run not found.", {"run_id": run_id}) from error
        row: RunRow | None = session.get(RunRow, key)
        if row is None:
            raise NotFoundError("Run not found.", {"run_id": run_id})
        return row
