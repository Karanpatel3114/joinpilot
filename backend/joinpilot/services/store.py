"""Project records stored as one JSON file per project folder.

A deliberately small store for M2; M5 moves project state to Postgres behind the
same methods.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from joinpilot.errors import NotFoundError

RECORD_FILE = "project.json"

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


class ProjectStore:
    """Create, list and update projects under `root/<project_id>/project.json`."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def project_dir(self, project_id: str) -> Path:
        """The project's folder; the id must be a UUID, which also blocks path tricks."""
        return self.root / str(uuid.UUID(project_id))

    def create(self, name: str) -> ProjectRecord:
        """Create and save a new, empty project."""
        record = ProjectRecord(id=str(uuid.uuid4()), name=name, created_at=datetime.now(UTC))
        self.save(record)
        return record

    def get(self, project_id: str) -> ProjectRecord:
        """Load one project, or raise NotFoundError."""
        try:
            path = self.project_dir(project_id) / RECORD_FILE
        except ValueError as error:
            raise NotFoundError("Project not found.", {"project_id": project_id}) from error
        if not path.exists():
            raise NotFoundError("Project not found.", {"project_id": project_id})
        return ProjectRecord.model_validate_json(path.read_text())

    def list_projects(self) -> list[ProjectRecord]:
        """All projects, newest first."""
        if not self.root.exists():
            return []
        records = [
            ProjectRecord.model_validate_json(p.read_text())
            for p in self.root.glob(f"*/{RECORD_FILE}")
        ]
        return sorted(records, key=lambda r: r.created_at, reverse=True)

    def save(self, record: ProjectRecord) -> None:
        """Write the record atomically, so readers never see a half-written file."""
        folder = self.project_dir(record.id)
        folder.mkdir(parents=True, exist_ok=True)
        write_atomic(folder / RECORD_FILE, json.dumps(record.model_dump(mode="json"), indent=2))
