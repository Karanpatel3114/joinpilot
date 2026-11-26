"""Run, proposal and approval endpoints (docs/contract.md, "Runs (agent)")."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse

from joinpilot.api.deps import get_run_service, guard_project_access
from joinpilot.api.schemas import (
    ApprovalRequest,
    CheckResult,
    CreateRunRequest,
    Dashboard,
    Metric,
    Run,
    RunProposal,
    View,
)
from joinpilot.services.runs import RunService
from joinpilot.sqlgen.export import Dialect, export_script, export_views

router = APIRouter(tags=["runs"], dependencies=[Depends(guard_project_access)])
Runs = Annotated[RunService, Depends(get_run_service)]


@router.post(
    "/projects/{project_id}/runs", response_model=Run, status_code=status.HTTP_202_ACCEPTED
)
async def start_run(project_id: UUID, body: CreateRunRequest, runs: Runs) -> Run:
    """Start an agent run; it profiles, ranks joins and then waits for approval."""
    record = await run_in_threadpool(runs.start, str(project_id), body.requirement)
    return Run.model_validate(record.model_dump())


@router.get("/projects/{project_id}/runs", response_model=list[Run])
async def list_runs(project_id: UUID, runs: Runs) -> list[Run]:
    """A project's runs, newest first."""
    records = await run_in_threadpool(runs.list_for_project, str(project_id))
    return [Run.model_validate(r.model_dump()) for r in records]


@router.get("/projects/{project_id}/dashboard", response_model=Dashboard)
async def get_dashboard(project_id: UUID, runs: Runs) -> Dashboard:
    """KPI metrics with their SQL and rows, from the newest completed run that has them."""
    run_id, metrics = await run_in_threadpool(runs.dashboard, str(project_id))
    return Dashboard(run_id=run_id, metrics=[Metric.model_validate(m) for m in metrics])


@router.get("/runs/{run_id}", response_model=Run)
async def get_run(run_id: UUID, runs: Runs) -> Run:
    """A run's status, parsed requirement, warnings and step timings (poll this)."""
    return Run.model_validate((await run_in_threadpool(runs.get, str(run_id))).model_dump())


@router.get("/runs/{run_id}/proposals", response_model=list[RunProposal])
async def get_proposals(run_id: UUID, runs: Runs) -> list[RunProposal]:
    """Proposed joins with evidence, explanation, recommendation and decision."""
    rows = await run_in_threadpool(runs.proposals, str(run_id))
    return [RunProposal.model_validate(p) for p in rows]


@router.post("/runs/{run_id}/approvals", response_model=Run, status_code=status.HTTP_202_ACCEPTED)
async def approve(run_id: UUID, body: ApprovalRequest, runs: Runs) -> Run:
    """Approve or reject joins on a waiting run; the run then resumes in the background."""
    record = await run_in_threadpool(runs.approve, str(run_id), body.decisions)
    return Run.model_validate(record.model_dump())


@router.get("/runs/{run_id}/views", response_model=list[View])
async def get_views(run_id: UUID, runs: Runs, dialect: Dialect = "duckdb") -> list[View]:
    """The views the run generated (after approval), with their SQL in the chosen dialect."""
    views = await run_in_threadpool(runs.views, str(run_id))
    return [View.model_validate(v) for v in export_views(views, dialect)]


@router.get("/runs/{run_id}/export", response_class=PlainTextResponse)
async def export_model(run_id: UUID, runs: Runs, dialect: Dialect = "duckdb") -> PlainTextResponse:
    """The whole model as one SQL script for Postgres, Snowflake, BigQuery or DuckDB."""
    views = await run_in_threadpool(runs.views, str(run_id))
    filename = f"joinpilot-{str(run_id)[:8]}-{dialect}.sql"
    return PlainTextResponse(
        export_script(views, dialect, str(run_id)),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/runs/{run_id}/checks", response_model=list[CheckResult])
async def get_checks(run_id: UUID, runs: Runs) -> list[CheckResult]:
    """The latest SIT check results of the run's views."""
    rows = await run_in_threadpool(runs.checks, str(run_id))
    return [CheckResult.model_validate(c) for c in rows]
