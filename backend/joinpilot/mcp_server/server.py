"""The MCP server: JoinPilot's workflow as tools for Claude Desktop, Claude Code and others.

Every tool calls the same services as the HTTP API (one service layer), and runs
jobs inline, so a tool returns once its step is done. The safety rules hold here
too: joins are built only after `approve_joins`, every question's SQL passes the
guard and runs read-only, and errors come back as tool errors in plain words.
Logs go to stderr; stdout carries the protocol.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field, StringConstraints

from joinpilot import __version__
from joinpilot.agent.approval import Decision
from joinpilot.config import Settings
from joinpilot.errors import ConflictError, InvalidInputError, JoinPilotError
from joinpilot.jobs.queue import InlineJobQueue
from joinpilot.qa.answer import Answer
from joinpilot.services.projects import ProjectService
from joinpilot.services.questions import QuestionService
from joinpilot.services.runs import RunService
from joinpilot.sqlgen.export import export_script

INSTRUCTIONS = """JoinPilot turns raw ERP tables and a plain-English requirement into a tested,
human-approved data model. Typical flow: list_projects (or create_project and
load_sample), profile_tables, propose_joins with the requirement, show the user the
proposals with their evidence, approve_joins only with the user's consent, then
get_check_results, get_dashboard and ask_question. Never approve joins on your own."""


# Input bounds advertised in the tool schemas; the services enforce the same rules.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Requirement = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)
]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
READ_ONLY = ToolAnnotations(read_only_hint=True)


class ProjectInfo(BaseModel):
    project_id: str
    name: str
    tables: list[str]


class ColumnInfo(BaseModel):
    name: str
    type: str
    null_rate: float
    distinct: int
    uniqueness: float | None


class TableInfo(BaseModel):
    name: str
    rows: int
    candidate_keys: list[list[str]]
    columns: list[ColumnInfo]


class ProfileInfo(BaseModel):
    project_id: str
    tables: list[TableInfo]
    overlaps: int = Field(description="Value overlaps found between columns of different tables")


class ProposalInfo(BaseModel):
    edge_id: str
    from_: str = Field(alias="from")
    to: str
    score: float
    recommended: bool
    cardinality: str
    normalization: str | None
    fan_out_risk: bool
    explanation: str
    status: str


class RunInfo(BaseModel):
    run_id: str
    status: str
    warnings: list[str]
    proposals: list[ProposalInfo] = Field(default_factory=list)
    views: list[dict[str, Any]] = Field(default_factory=list)
    checks_passed: int = 0
    checks_total: int = 0
    failed_checks: list[str] = Field(default_factory=list)
    error: str | None = None


class CheckInfo(BaseModel):
    check_id: str
    passed: bool
    observed: float | str | None
    expected: float | str | None
    message: str


class DashboardInfo(BaseModel):
    run_id: str | None
    metrics: list[dict[str, Any]]


def plain_errors[**P, R](tool: Callable[P, R]) -> Callable[P, R]:
    """Turn JoinPilot's domain errors into MCP tool errors with their plain message."""

    @wraps(tool)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return tool(*args, **kwargs)
        except JoinPilotError as error:
            raise ToolError(f"{error.code}: {error.message}") from error

    return wrapper


def build_server(settings: Settings) -> MCPServer:
    """An MCP server bound to these settings; jobs run inline in this process."""
    projects = ProjectService(settings)
    runs = RunService(settings, InlineJobQueue(settings))
    questions = QuestionService(settings, runs)
    server = MCPServer(name="JoinPilot", version=__version__, instructions=INSTRUCTIONS)

    def run_info(run_id: str) -> RunInfo:
        record = runs.get(run_id)
        checks = runs.checks(run_id)
        return RunInfo(
            run_id=run_id,
            status=record.status,
            warnings=record.warnings,
            error=record.error,
            proposals=[ProposalInfo.model_validate(p) for p in runs.proposals(run_id)],
            views=[
                {k: v[k] for k in ("name", "status", "fact_table", "message")}
                for v in runs.views(run_id)
            ],
            checks_passed=sum(c["passed"] for c in checks),
            checks_total=len(checks),
            failed_checks=[c["message"] for c in checks if not c["passed"]],
        )

    @server.tool(annotations=READ_ONLY)
    @plain_errors
    def list_projects() -> list[ProjectInfo]:
        """List JoinPilot projects with their tables."""
        return [
            ProjectInfo(project_id=p.id, name=p.name, tables=[t.name for t in p.tables])
            for p in projects.list_projects()
        ]

    @server.tool()
    @plain_errors
    def create_project(name: Name) -> ProjectInfo:
        """Create an empty project."""
        record = projects.create(name)
        return ProjectInfo(project_id=record.id, name=record.name, tables=[])

    @server.tool()
    @plain_errors
    def load_sample(project_id: str) -> ProjectInfo:
        """Load the synthetic SAP-style ERP sample (six tables with planted data-quality issues)."""
        projects.add_sample(project_id, "erp_s1_sap")
        record = projects.get(project_id)
        return ProjectInfo(
            project_id=record.id, name=record.name, tables=[t.name for t in record.tables]
        )

    @server.tool(annotations=READ_ONLY)
    @plain_errors
    def profile_tables(project_id: str) -> ProfileInfo:
        """Profile every table: row counts, candidate keys, and per column its type, null
        rate, distinct values and uniqueness."""
        profile = projects.profile(project_id)
        uniqueness = {
            (k.table, k.columns[0]): k.uniqueness for k in profile.keys if len(k.columns) == 1
        }
        return ProfileInfo(
            project_id=project_id,
            overlaps=len(profile.overlaps),
            tables=[
                TableInfo(
                    name=t.name,
                    rows=t.row_count,
                    candidate_keys=t.candidate_keys,
                    columns=[
                        ColumnInfo(
                            name=c.name,
                            type=c.type,
                            null_rate=round(c.null_pct, 4),
                            distinct=c.distinct_count,
                            uniqueness=uniqueness.get((t.name, c.name)),
                        )
                        for c in t.columns
                    ],
                )
                for t in profile.tables
            ],
        )

    @server.tool()
    @plain_errors
    def propose_joins(project_id: str, requirement: Requirement) -> RunInfo:
        """Start a run for a business requirement. It profiles the tables, ranks join
        candidates with evidence and stops for approval (status awaiting_approval); nothing
        is built yet. With no join candidates the run completes at once with no proposals."""
        return run_info(runs.start(project_id, requirement).run_id)

    @server.tool()
    @plain_errors
    def approve_joins(
        run_id: str,
        approve: Annotated[list[str], Field(min_length=1, max_length=200)] | None = None,
        reject_reason: Reason | None = None,
    ) -> RunInfo:
        """Approve joins by edge id (omit `approve` for the recommended ones) and reject the
        rest, then build the views, run the checks (with repair) and build the dashboard.
        Edge ids must come from propose_joins or get_run. Only call this after the user
        has agreed to the joins."""
        proposals = runs.proposals(run_id)
        if not proposals:
            raise ConflictError("This run has no joins to approve.")
        known = {p["edge_id"] for p in proposals}
        if approve is not None and (unknown := sorted(set(approve) - known)):
            raise InvalidInputError(
                f"Unknown join ids: {', '.join(unknown)}. "
                "Use edge_id values from propose_joins or get_run."
            )
        chosen = (
            set(approve)
            if approve is not None
            else {p["edge_id"] for p in proposals if p["recommended"]}
        )
        decisions = [
            Decision(
                edge_id=p["edge_id"],
                action="approve" if p["edge_id"] in chosen else "reject",
                reason=None if p["edge_id"] in chosen else reject_reason,
            )
            for p in proposals
        ]
        runs.approve(run_id, decisions)
        return run_info(run_id)

    @server.tool(annotations=READ_ONLY)
    @plain_errors
    def get_run(run_id: str) -> RunInfo:
        """A run's status, proposals, views and check summary."""
        return run_info(run_id)

    @server.tool(annotations=READ_ONLY)
    @plain_errors
    def get_check_results(run_id: str) -> list[CheckInfo]:
        """Every automated check on the run's views: row counts, fan-out, orphan and null
        keys, aging bucket coverage and money reconciliation."""
        return [CheckInfo.model_validate(c) for c in runs.checks(run_id)]

    @server.tool(annotations=READ_ONLY)
    @plain_errors
    def get_dashboard(project_id: str) -> DashboardInfo:
        """The KPI dashboard of the project's newest completed run, with each metric's SQL."""
        run_id, metrics = runs.dashboard(project_id)
        return DashboardInfo(run_id=run_id, metrics=metrics)

    @server.tool()
    @plain_errors
    def ask_question(project_id: str, question: str) -> Answer:
        """Answer a business question with guarded, read-only SQL over the tested model.
        The answer includes the SQL, the rows and where they came from."""
        return questions.ask(project_id, question)

    @server.tool(annotations=READ_ONLY)
    @plain_errors
    def export_sql(
        run_id: str, dialect: Literal["duckdb", "postgres", "snowflake", "bigquery"] = "duckdb"
    ) -> str:
        """The run's data model as one SQL script for DuckDB, Postgres, Snowflake or BigQuery."""
        return export_script(runs.views(run_id), dialect, run_id)

    return server
