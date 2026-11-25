"""Pydantic request and response models. They mirror docs/contract.md exactly."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from joinpilot.profiling.models import (
    ColumnProfile,
    KeyEvidence,
    Overlap,
    ProjectProfile,
    TableProfile,
)

__all__ = [
    "ColumnProfile",
    "CreateProjectRequest",
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    "KeyEvidence",
    "Overlap",
    "Project",
    "ProjectProfile",
    "SampleRequest",
    "TableProfile",
    "TableSummary",
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
