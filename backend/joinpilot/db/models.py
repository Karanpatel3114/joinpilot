"""Application state in Postgres (SQLite locally and in tests): projects, their tables,
agent runs, join proposals with their decisions, and model-call usage.

Analytics data never lives here; it stays in each project's DuckDB file (D-001).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JSONValue = JSON().with_variant(JSONB(), "postgresql")


def utc_now() -> datetime:
    """Timezone-aware current time."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base with JSON columns mapped to JSONB on Postgres."""

    type_annotation_map: ClassVar[dict[Any, Any]] = {
        dict[str, Any]: JSONValue,
        list[Any]: JSONValue,
    }


class ProjectRow(Base):
    """A project; its warehouse is a DuckDB file in the project folder."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    tables: Mapped[list[TableRow]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="TableRow.name"
    )


class TableRow(Base):
    """A table loaded into a project's warehouse."""

    __tablename__ = "project_tables"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(63))
    row_count: Mapped[int] = mapped_column(Integer)
    column_count: Mapped[int] = mapped_column(Integer)
    project: Mapped[ProjectRow] = relationship(back_populates="tables")


class RunRow(Base):
    """One agent run: a requirement turned into proposals, approvals, views and checks."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    requirement: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), index=True)
    parsed_requirement: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings: Mapped[list[Any]] = mapped_column(default=list)
    timings_ms: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    proposals: Mapped[list[ProposalRow]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="ProposalRow.position"
    )


class ProposalRow(Base):
    """A proposed join, its evidence and explanation, and the person's decision."""

    __tablename__ = "proposals"
    __table_args__ = (UniqueConstraint("run_id", "edge_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    edge_id: Mapped[str] = mapped_column(String(16))
    position: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column()
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run: Mapped[RunRow] = relationship(back_populates="proposals")


class LLMCallRow(Base):
    """Usage of one model call: tokens, latency, estimated cost (never prompt text)."""

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    purpose: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
