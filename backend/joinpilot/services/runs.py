"""Agent runs: start one, follow its status, read proposals, approve, resume.

A run is a small state machine stored in the `runs` table. Every status change is a
compare-and-set update, so concurrent approvals or a redelivered job cannot move a
run backwards, and terminal states (completed, failed) never change. The graph's
own state lives in the checkpointer; jobs read it first, which makes them safe to
run twice: a duplicate start or resume finds the work done and does nothing.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from langgraph.types import Command
from pydantic import BaseModel
from sqlalchemy import delete, select, update

from joinpilot.agent.approval import Decision
from joinpilot.agent.checkpoints import open_checkpointer
from joinpilot.agent.graph import AgentContext, build_graph
from joinpilot.agent.requirement import ParsedRequirement
from joinpilot.config import Settings
from joinpilot.db.models import (
    CheckResultRow,
    LLMCallRow,
    ProposalRow,
    RunMetricRow,
    RunRow,
    RunViewRow,
)
from joinpilot.db.session import ensure_migrated, session_scope
from joinpilot.errors import (
    ConflictError,
    InvalidInputError,
    JobQueueUnavailableError,
    JoinPilotError,
    NotFoundError,
)
from joinpilot.jobs.queue import JobQueue
from joinpilot.llm.factory import make_provider
from joinpilot.llm.observed import UsageLog
from joinpilot.services.projects import ProjectService

logger = logging.getLogger(__name__)

TERMINAL = frozenset({"completed", "failed"})
ACTIVE = frozenset({"queued", "profiling", "ranking", "generating", "checking", "repairing"})
# Same bounds as the API's request model, for every caller (API, MCP).
MIN_REQUIREMENT_CHARS, MAX_REQUIREMENT_CHARS = 3, 2000
# Steps that write the project's model views; only one run per project may be in them.
BUILDING = frozenset({"generating", "checking", "repairing"})
# Mirroring graph state may only move a run forward along this order.
ORDER = {
    "queued": 0,
    "profiling": 1,
    "ranking": 2,
    "awaiting_approval": 3,
    "generating": 4,
    "checking": 5,
    "repairing": 5,
    "completed": 9,
    "failed": 9,
}
PAUSED_AT = ("await_approval",)

_RUN_LOCKS: dict[str, threading.Lock] = {}
_RUN_LOCKS_GUARD = threading.Lock()


def run_lock(run_id: str) -> threading.Lock:
    """One lock per run, so two jobs in this process never drive the same run at once."""
    with _RUN_LOCKS_GUARD:
        return _RUN_LOCKS.setdefault(run_id, threading.Lock())


class RunRecord(BaseModel):
    """What the API returns for a run."""

    run_id: str
    project_id: str
    status: str
    requirement: str
    parsed_requirement: ParsedRequirement | None
    error: str | None
    warnings: list[str]
    timings_ms: dict[str, float]
    created_at: datetime
    updated_at: datetime


def aware(value: datetime) -> datetime:
    """Timezone-aware (SQLite drops the zone)."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def to_record(row: RunRow) -> RunRecord:
    """Map a run row to its record."""
    return RunRecord(
        run_id=row.id,
        project_id=row.project_id,
        status=row.status,
        requirement=row.requirement,
        parsed_requirement=(
            ParsedRequirement.model_validate(row.parsed_requirement)
            if row.parsed_requirement
            else None
        ),
        error=row.error,
        warnings=list(row.warnings),
        timings_ms=dict(row.timings_ms),
        created_at=aware(row.created_at),
        updated_at=aware(row.updated_at),
    )


def thread(run_id: str) -> Any:
    """LangGraph config: one checkpoint thread per run."""
    return {"configurable": {"thread_id": run_id}}


def safe_message(error: Exception) -> str:
    """A message fit for users: domain errors explain themselves, others stay in the log."""
    if isinstance(error, JoinPilotError):
        return error.message
    return f"The run failed unexpectedly ({type(error).__name__}); the server log has details."


class RunService:
    """Every run operation the API, the worker and the MCP server need."""

    def __init__(self, settings: Settings, jobs: JobQueue) -> None:
        self.settings = settings
        self.jobs = jobs
        self.projects = ProjectService(settings)
        ensure_migrated(settings.db_url)

    # ----- requests -------------------------------------------------------------

    def start(self, project_id: str, requirement: str) -> RunRecord:
        """Create a run for a project with tables, and queue its first job."""
        requirement = requirement.strip()
        if not MIN_REQUIREMENT_CHARS <= len(requirement) <= MAX_REQUIREMENT_CHARS:
            raise InvalidInputError(
                f"A requirement needs {MIN_REQUIREMENT_CHARS} to {MAX_REQUIREMENT_CHARS} "
                "characters.",
                {"field": "requirement"},
            )
        project = self.projects.get(project_id)
        if not project.tables:
            raise ConflictError("Load at least one table before starting a run.")
        run_id = str(uuid.uuid4())
        with session_scope(self.settings.db_url) as session:
            session.add(
                RunRow(id=run_id, project_id=project.id, requirement=requirement, status="queued")
            )
        try:
            self.jobs.submit("start_run", run_id)
        except Exception as error:
            logger.exception("could not queue run %s", run_id)
            self._fail(run_id, "The run could not be queued.")
            raise JobQueueUnavailableError("The job queue is unavailable; try again.") from error
        return self.get(run_id)

    def approve(self, run_id: str, decisions: list[Decision]) -> RunRecord:
        """Record decisions on a paused run (once), then queue the resume."""
        if not decisions:
            raise InvalidInputError("Send at least one decision.")
        decided = self._record_decisions(run_id, decisions)
        try:
            self.jobs.submit("resume_run", run_id)
        except Exception as error:
            logger.exception("could not queue the resume of run %s", run_id)
            self._undo_decisions(run_id, decided)
            raise JobQueueUnavailableError(
                "The job queue is unavailable; your decisions were not applied, try again."
            ) from error
        return self.get(run_id)

    def get(self, run_id: str) -> RunRecord:
        """One run, or NotFoundError."""
        with session_scope(self.settings.db_url) as session:
            return to_record(self._row(session, run_id))

    def list_for_project(self, project_id: str) -> list[RunRecord]:
        """A project's runs, newest first."""
        self.projects.get(project_id)
        query = select(RunRow).where(RunRow.project_id == project_id)
        with session_scope(self.settings.db_url) as session:
            rows = session.scalars(query.order_by(RunRow.created_at.desc(), RunRow.id))
            return [to_record(r) for r in rows]

    def proposals(self, run_id: str) -> list[dict[str, Any]]:
        """The run's proposals with their current status and decision."""
        with session_scope(self.settings.db_url) as session:
            row = self._row(session, run_id)
            return [
                {**p.payload, "status": p.status, "decision_reason": p.decision_reason}
                for p in row.proposals
            ]

    # ----- jobs -------------------------------------------------------------------

    def execute(self, run_id: str) -> None:
        """Job body for `start_run`: move the run forward from wherever it is."""
        self.advance(run_id)

    def resume(self, run_id: str) -> None:
        """Job body for `resume_run`: move the run forward from wherever it is."""
        self.advance(run_id)

    def advance(self, run_id: str) -> None:
        """Drive the graph from its saved checkpoint; a no-op when there is nothing to do.

        A fresh run starts; a run paused for approval resumes only once decisions are
        recorded (status `generating`); a run interrupted by a restart continues; a
        finished run is left alone. This is what makes duplicate jobs harmless.
        """
        with run_lock(run_id):
            try:
                run = self.get(run_id)
                if run.status in TERMINAL:
                    return
                self._advance(run)
            except Exception as error:
                logger.exception("run %s failed", run_id)
                self._fail(run_id, safe_message(error))

    def recover(self) -> int:
        """Re-queue runs a restart left active (thread mode loses its queue); returns the count."""
        with session_scope(self.settings.db_url) as session:
            stuck = [r.id for r in session.scalars(select(RunRow).where(RunRow.status.in_(ACTIVE)))]
        for run_id in stuck:
            self.jobs.submit("resume_run", run_id)
        return len(stuck)

    # ----- internals ----------------------------------------------------------------

    def _advance(self, run: RunRecord) -> None:
        log = UsageLog()
        ctx = AgentContext(
            load_profile=lambda: self.projects.profile(run.project_id),
            llm=make_provider(self.settings, log),
            settings=self.settings,
            warehouse=lambda: self.projects.warehouse(run.project_id),
        )
        with open_checkpointer(self.settings) as saver:
            graph = build_graph(ctx, saver)
            snapshot = graph.get_state(thread(run.run_id))
            if not snapshot.values:
                self._transition(run.run_id, {"queued"}, "profiling")
                graph_input: Any = {
                    "run_id": run.run_id,
                    "project_id": run.project_id,
                    "requirement": run.requirement,
                    "status": "profiling",
                }
            elif tuple(snapshot.next) == PAUSED_AT:
                if run.status != "generating":
                    self._transition(run.run_id, ACTIVE, "awaiting_approval")
                    return
                graph_input = Command(resume=self._decisions(run.run_id))
            elif snapshot.next:
                graph_input = None
            else:
                return
            for values in graph.stream(
                graph_input, thread(run.run_id), stream_mode="values", durability="sync"
            ):
                self._mirror(run.run_id, values)
                self._save_usage(run.run_id, log)
            after = graph.get_state(thread(run.run_id))
        if tuple(after.next) == PAUSED_AT:
            self._transition(run.run_id, ACTIVE, "awaiting_approval")
        elif not after.next:
            final = str(after.values.get("status", "completed"))
            self._transition(run.run_id, ACTIVE, final if final in TERMINAL else "completed")

    def _decisions(self, run_id: str) -> list[dict[str, Any]]:
        return [
            {
                "edge_id": p["edge_id"],
                "reason": p.get("decision_reason"),
                "action": "approve" if p["status"] == "approved" else "reject",
            }
            for p in self.proposals(run_id)
            if p["status"] in ("approved", "rejected")
        ]

    def _record_decisions(self, run_id: str, decisions: list[Decision]) -> list[str]:
        """Claim the paused run (compare-and-set) and store decisions in one transaction.

        Views share one model schema per project, so a run may only start building while
        no other run of its project is building (checked under a per-project lock).
        """
        with session_scope(self.settings.db_url) as session:
            project_id = self._row(session, run_id).project_id
        with run_lock(f"build:{project_id}"), session_scope(self.settings.db_url) as session:
            row = self._row(session, run_id)
            known = {p.edge_id: p for p in row.proposals}
            unknown = sorted({d.edge_id for d in decisions} - set(known))
            if unknown:
                raise InvalidInputError("Some decisions name unknown joins.", {"edge_ids": unknown})
            building = session.scalars(
                select(RunRow.id).where(
                    RunRow.project_id == row.project_id,
                    RunRow.id != row.id,
                    RunRow.status.in_(BUILDING),
                )
            ).first()
            if building is not None and row.status == "awaiting_approval":
                raise ConflictError(
                    "Another run in this project is building its model; approve this one "
                    "when it finishes.",
                    {"run_id": building},
                )
            claimed = session.execute(
                update(RunRow)
                .where(RunRow.id == row.id, RunRow.status == "awaiting_approval")
                .values(status="generating", updated_at=datetime.now(UTC))
            )
            if claimed.rowcount != 1:  # type: ignore[attr-defined]
                raise ConflictError("This run is not waiting for approval.", {"status": row.status})
            now = datetime.now(UTC)
            for d in decisions:
                proposal = known[d.edge_id]
                proposal.status = "approved" if d.action == "approve" else "rejected"
                proposal.decision_reason, proposal.decided_at = d.reason, now
            return [d.edge_id for d in decisions]

    def _undo_decisions(self, run_id: str, edge_ids: list[str]) -> None:
        with session_scope(self.settings.db_url) as session:
            row = self._row(session, run_id)
            for proposal in row.proposals:
                if proposal.edge_id in edge_ids:
                    proposal.status, proposal.decision_reason, proposal.decided_at = (
                        "proposed",
                        None,
                        None,
                    )
        self._transition(run_id, {"generating"}, "awaiting_approval")

    def _transition(self, run_id: str, allowed: set[str] | frozenset[str], to: str) -> bool:
        """Compare-and-set the status; True if this call made the change."""
        with session_scope(self.settings.db_url) as session:
            result = session.execute(
                update(RunRow)
                .where(RunRow.id == run_id, RunRow.status.in_(allowed))
                .values(status=to, updated_at=datetime.now(UTC))
            )
            return bool(result.rowcount == 1)  # type: ignore[attr-defined]

    def _mirror(self, run_id: str, values: dict[str, Any]) -> None:
        """Copy the latest state into the run row and its proposals, only ever forward."""
        with session_scope(self.settings.db_url) as session:
            row = self._row(session, run_id)
            status = values.get("status")
            moves_forward = status in ORDER and ORDER[status] >= ORDER.get(row.status, 0)
            if status and row.status not in TERMINAL and moves_forward and status in ACTIVE:
                row.status = status
            row.parsed_requirement = values.get("parsed_requirement", row.parsed_requirement)
            row.warnings = list(values.get("warnings", row.warnings))
            row.timings_ms = dict(values.get("timings_ms", row.timings_ms))
            self._mirror_outputs(session, row.id, values)
            existing = {p.edge_id for p in row.proposals}
            for position, proposal in enumerate(values.get("proposals", [])):
                if proposal["edge_id"] not in existing:
                    row.proposals.append(
                        ProposalRow(
                            edge_id=proposal["edge_id"],
                            position=position,
                            payload={k: v for k, v in proposal.items() if k != "status"},
                            status="proposed",
                        )
                    )

    @staticmethod
    def _mirror_outputs(session: Any, run_id: str, values: dict[str, Any]) -> None:
        """Replace the run's stored views, check results and metrics with the latest ones."""
        if "views" in values:
            session.execute(delete(RunViewRow).where(RunViewRow.run_id == run_id))
            session.add_all(
                RunViewRow(run_id=run_id, name=v["name"], position=i, payload=v)
                for i, v in enumerate(values["views"])
            )
        if "checks" in values:
            session.execute(delete(CheckResultRow).where(CheckResultRow.run_id == run_id))
            session.add_all(
                CheckResultRow(
                    run_id=run_id, check_id=c["check_id"], position=i, passed=c["passed"], payload=c
                )
                for i, c in enumerate(values["checks"])
            )
        if "metrics" in values:
            session.execute(delete(RunMetricRow).where(RunMetricRow.run_id == run_id))
            session.add_all(
                RunMetricRow(run_id=run_id, metric_id=m["metric_id"], position=i, payload=m)
                for i, m in enumerate(values["metrics"])
            )

    def views(self, run_id: str) -> list[dict[str, Any]]:
        """The views the run generated, in order."""
        with session_scope(self.settings.db_url) as session:
            row = self._row(session, run_id)
            query = select(RunViewRow).where(RunViewRow.run_id == row.id)
            return [dict(v.payload) for v in session.scalars(query.order_by(RunViewRow.position))]

    def dashboard(self, project_id: str) -> tuple[str | None, list[dict[str, Any]]]:
        """The metrics of the project's most recently completed run, and that run.

        The newest model is the one in the warehouse, so an older run's numbers are never
        shown in its place, even when the newest run produced no metrics.
        """
        self.projects.get(project_id)
        query = (
            select(RunRow.id)
            .where(RunRow.project_id == project_id, RunRow.status == "completed")
            .order_by(RunRow.updated_at.desc(), RunRow.id)
            .limit(1)
        )
        with session_scope(self.settings.db_url) as session:
            run_id = session.scalars(query).first()
            if run_id is None:
                return None, []
            rows = select(RunMetricRow).where(RunMetricRow.run_id == run_id)
            metrics = session.scalars(rows.order_by(RunMetricRow.position))
            return run_id, [dict(m.payload) for m in metrics]

    def model_conflict(self, project_id: str) -> str | None:
        """Why the warehouse's model views may not match the newest completed run, if so.

        A run that is building has replaced or is replacing the views, and a run that
        failed after creating views left them unchecked; either way answers would cite
        one run and read another's views.
        """
        newest_with_views = (
            select(RunRow.status)
            .join(RunViewRow, RunViewRow.run_id == RunRow.id)
            .where(RunRow.project_id == project_id)
            .order_by(RunRow.updated_at.desc(), RunRow.id)
            .limit(1)
        )
        building = select(RunRow.id).where(
            RunRow.project_id == project_id, RunRow.status.in_(BUILDING)
        )
        with session_scope(self.settings.db_url) as session:
            if session.scalars(building).first() is not None:
                return "A run is building this project's model; ask again when it finishes."
            if session.scalars(newest_with_views).first() == "failed":
                return (
                    "The newest run failed after creating its views, so they are unchecked; "
                    "start a new run before asking questions."
                )
        return None

    def checks(self, run_id: str) -> list[dict[str, Any]]:
        """The latest check results of the run's views, in order."""
        with session_scope(self.settings.db_url) as session:
            row = self._row(session, run_id)
            query = select(CheckResultRow).where(CheckResultRow.run_id == row.id)
            ordered = query.order_by(CheckResultRow.position)
            return [dict(c.payload) for c in session.scalars(ordered)]

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
        """Mark an active or paused run failed with a user-safe message."""
        with session_scope(self.settings.db_url) as session:
            session.execute(
                update(RunRow)
                .where(RunRow.id == run_id, RunRow.status.not_in(TERMINAL))
                .values(status="failed", error=message[:2000], updated_at=datetime.now(UTC))
            )

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
