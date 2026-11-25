"""Project records in the application database (Postgres, or SQLite locally).

Each project also has a folder for its DuckDB warehouse and cached profile.
"""

from __future__ import annotations

import os
import tempfile
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from joinpilot.db.models import ProjectRow, TableRow
from joinpilot.db.session import ensure_migrated, session_scope
from joinpilot.errors import NotFoundError

_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def project_lock(project_id: str) -> threading.RLock:
    """One lock per project, so reads, changes and writes of its state never interleave.

    This protects one API process. A single process owns each project's DuckDB file
    for writing (DuckDB allows one writer process), so this is the right scope.
    """
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(project_id, threading.RLock())


def write_atomic(path: Path, text: str) -> None:
    """Write `text` to a unique temporary file, then rename it over `path`."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class TableRecord(BaseModel):
    """A loaded table: its stable id, name and size."""

    table_id: str
    name: str
    row_count: int
    column_count: int


class ProjectRecord(BaseModel):
    """A project and the tables loaded into its warehouse."""

    id: str
    name: str
    created_at: datetime
    tables: list[TableRecord] = Field(default_factory=list)


def to_record(row: ProjectRow) -> ProjectRecord:
    """Map a database row to the service's record."""
    created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=UTC)
    return ProjectRecord(
        id=row.id,
        name=row.name,
        created_at=created,
        tables=[
            TableRecord(
                table_id=t.id, name=t.name, row_count=t.row_count, column_count=t.column_count
            )
            for t in row.tables
        ],
    )


def parse_id(project_id: str) -> str:
    """The canonical form of a project id, or NotFoundError for anything that is not a UUID."""
    try:
        return str(uuid.UUID(project_id))
    except ValueError as error:
        raise NotFoundError("Project not found.", {"project_id": project_id}) from error


class ProjectStore:
    """Create, list and update projects; their folders live under `root`."""

    def __init__(self, root: Path, db_url: str) -> None:
        self.root = root
        self.db_url = db_url
        ensure_migrated(db_url)

    def project_dir(self, project_id: str) -> Path:
        """The project's folder; the id must be a UUID, which also blocks path tricks."""
        return self.root / parse_id(project_id)

    def create(self, name: str) -> ProjectRecord:
        """Create and save a new, empty project."""
        row = ProjectRow(id=str(uuid.uuid4()), name=name, created_at=datetime.now(UTC))
        with session_scope(self.db_url) as session:
            session.add(row)
            session.flush()
            return to_record(row)

    def get(self, project_id: str) -> ProjectRecord:
        """Load one project, or raise NotFoundError."""
        key = parse_id(project_id)
        with session_scope(self.db_url) as session:
            row = session.get(ProjectRow, key, options=[selectinload(ProjectRow.tables)])
            if row is None:
                raise NotFoundError("Project not found.", {"project_id": project_id})
            return to_record(row)

    def list_projects(self) -> list[ProjectRecord]:
        """All projects, newest first."""
        query = (
            select(ProjectRow)
            .options(selectinload(ProjectRow.tables))
            .order_by(ProjectRow.created_at.desc(), ProjectRow.id)
        )
        with session_scope(self.db_url) as session:
            return [to_record(row) for row in session.scalars(query)]

    def save(self, record: ProjectRecord) -> None:
        """Write the project's name and table list in one transaction."""
        with session_scope(self.db_url) as session:
            row = session.get(ProjectRow, record.id, options=[selectinload(ProjectRow.tables)])
            if row is None:
                raise NotFoundError("Project not found.", {"project_id": record.id})
            row.name = record.name
            wanted = {t.table_id: t for t in record.tables}
            for stale in [t for t in row.tables if t.id not in wanted]:
                row.tables.remove(stale)
            session.flush()  # deletes first, so a freed name can be reused below
            existing = {t.id: t for t in row.tables}
            for table_id, table in wanted.items():
                current = existing.get(table_id)
                if current is None:
                    current = TableRow(id=table_id)
                    row.tables.append(current)
                current.name, current.row_count = table.name, table.row_count
                current.column_count = table.column_count
