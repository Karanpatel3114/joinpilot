"""Pydantic request and response models. They mirror docs/contract.md exactly."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from joinpilot.agent.approval import Decision
from joinpilot.agent.ranking import Proposal
from joinpilot.agent.requirement import ParsedRequirement
from joinpilot.checks.sit import CheckResult
from joinpilot.glossary.service import GlossaryMatch
from joinpilot.profiling.models import (
    ColumnProfile,
    KeyEvidence,
    Overlap,
    ProjectProfile,
    TableProfile,
)
from joinpilot.sqlgen.views import View

__all__ = [
    "ApprovalRequest",
    "CheckResult",
    "ColumnProfile",
    "CreateProjectRequest",
    "CreateRunRequest",
    "Decision",
    "ErrorDetail",
    "ErrorResponse",
    "GlossaryMatch",
    "HealthResponse",
    "KeyEvidence",
    "Overlap",
    "Project",
    "ProjectProfile",
    "Run",
    "RunProposal",
    "SampleRequest",
    "TableProfile",
    "TableSummary",
    "View",
]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)


class Project(BaseModel):
    id: str
    name: str
    created_at: datetime
    table_count: int


class SampleRequest(BaseModel):
    sample: str = Field(examples=["erp_s1_sap"])


class TableSummary(BaseModel):
    table_id: str
    name: str
    row_count: int
    column_count: int


RunStatus = Literal[
    "queued",
    "profiling",
    "ranking",
    "awaiting_approval",
    "generating",
    "checking",
    "repairing",
    "completed",
    "failed",
]


class CreateRunRequest(BaseModel):
    """Start a run for this requirement."""

    model_config = ConfigDict(str_strip_whitespace=True)

    requirement: str = Field(min_length=3, max_length=2000)


class Run(BaseModel):
    """A run's state; poll it to follow progress."""

    run_id: str
    project_id: str
    status: RunStatus
    requirement: str
    parsed_requirement: ParsedRequirement | None
    error: str | None
    warnings: list[str]
    timings_ms: dict[str, float]
    created_at: datetime
    updated_at: datetime


class RunProposal(Proposal):
    """A proposal as stored for a run, with the person's decision."""

    decision_reason: str | None = None


class ApprovalRequest(BaseModel):
    """Decisions on a paused run's proposals."""

    decisions: list[Decision] = Field(min_length=1, max_length=200)
