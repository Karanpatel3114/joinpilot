"""Projects: create and list them, add tables (uploads or the sample), and profile them."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

import duckdb
from sqlalchemy import delete

from joinpilot.config import Settings
from joinpilot.db.models import GlossaryRow
from joinpilot.db.session import session_scope
from joinpilot.errors import InvalidInputError, PayloadTooLargeError
from joinpilot.profiling.loader import (
    SUPPORTED_SUFFIXES,
    LoadedTable,
    connect,
    load_arrow,
    load_file,
    table_name_from_filename,
)
from joinpilot.profiling.models import ProjectProfile
from joinpilot.profiling.service import profile_project
from joinpilot.services.store import (
    ProjectRecord,
    ProjectStore,
    TableRecord,
    project_lock,
    write_atomic,
)
from joinpilot.synth.dataset import build_dataset
from joinpilot.synth.naming import Naming

PROFILE_FILE = "profile.json"
SAMPLE_PATTERN = re.compile(r"^erp_(?P<size>[a-z])(?P<seed>\d{1,4})_(?P<naming>sap|friendly)$")
CHUNK_BYTES = 1024 * 1024


def existing_name(record: ProjectRecord, name: str) -> str:
    """Reuse an existing table's spelling when names differ only by case.

    DuckDB identifiers ignore case, so `vbak` would replace `VBAK`; keeping one
    spelling keeps the store and the warehouse in step.
    """
    for table in record.tables:
        if table.name.casefold() == name.casefold():
            return table.name
    return name


# Same bounds as the API's request models, for every caller (API, MCP).
MAX_NAME_CHARS = 100


class ProjectService:
    """Every project operation the API, worker, MCP server and evaluation need."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = ProjectStore(settings.projects_dir, settings.db_url)

    def create(self, name: str) -> ProjectRecord:
        """Create an empty project (a name of 1 to 100 characters)."""
        name = name.strip()
        if not 1 <= len(name) <= MAX_NAME_CHARS:
            raise InvalidInputError(
                f"A project name needs 1 to {MAX_NAME_CHARS} characters.", {"field": "name"}
            )
        return self.store.create(name)

    def list_projects(self) -> list[ProjectRecord]:
        """All projects, newest first."""
        return self.store.list_projects()

    def get(self, project_id: str) -> ProjectRecord:
        """One project, or NotFoundError."""
        return self.store.get(project_id)

    def check_upload_names(self, filenames: list[str]) -> None:
        """Refuse a batch up front if any file has an unsupported type."""
        for filename in filenames:
            if Path(filename).suffix.lower() not in SUPPORTED_SUFFIXES:
                raise InvalidInputError(
                    "Only CSV and Parquet files are supported.", {"file": filename}
                )

    def add_upload(self, project_id: str, filename: str, stream: BinaryIO) -> list[TableRecord]:
        """Save one uploaded file (within the size limit), load it, and drop the copy."""
        self.check_upload_names([filename])
        suffix = Path(filename).suffix.lower()
        self.store.get(project_id)
        folder = self.store.project_dir(project_id) / "uploads"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{uuid.uuid4()}{suffix}"
        try:
            self._copy_limited(stream, path)
            with project_lock(project_id):
                record = self.store.get(project_id)
                table = existing_name(record, table_name_from_filename(filename))
                self._check_capacity(record, [table])
                with self._connect(project_id) as con:
                    loaded = load_file(
                        con,
                        path,
                        table,
                        display_name=filename,
                        max_columns=self.settings.max_columns_per_table,
                    )
                return self._register(record, [loaded])
        finally:
            path.unlink(missing_ok=True)

    def add_sample(self, project_id: str, sample: str) -> list[TableRecord]:
        """Generate a synthetic ERP dataset (no gold) and load its tables."""
        self.store.get(project_id)
        match = SAMPLE_PATTERN.match(sample)
        size = match["size"].upper() if match else ""
        if not match or size not in self.settings.sample_sizes:
            raise InvalidInputError(
                "Unknown sample dataset.",
                {"sample": sample, "allowed_sizes": self.settings.sample_sizes},
            )
        naming: Naming = "sap" if match["naming"] == "sap" else "friendly"
        tables = build_dataset(
            int(match["seed"]), size, naming, self.settings.synth
        ).output_tables()
        with project_lock(project_id):
            record = self.store.get(project_id)
            names = {name: existing_name(record, name) for name in tables}
            self._check_capacity(record, list(names.values()))
            with self._connect(project_id) as con:
                loaded = [load_arrow(con, names[name], data) for name, data in tables.items()]
            return self._register(record, loaded)

    def profile(self, project_id: str) -> ProjectProfile:
        """Return the cached profile, computing it after any table change."""
        with project_lock(project_id):
            record = self.store.get(project_id)
            cache = self.store.project_dir(project_id) / PROFILE_FILE
            if cache.exists():
                return ProjectProfile.model_validate_json(cache.read_text())
            tables = {t.table_id: t.name for t in record.tables}
            with self._connect(project_id) as con:
                profile = profile_project(con, tables, self.settings.profiling)
            write_atomic(cache, profile.model_dump_json(by_alias=True))
            return profile

    def _register(self, record: ProjectRecord, loaded: list[LoadedTable]) -> list[TableRecord]:
        """Add or replace table records and drop the cached profile; caller holds the lock."""
        existing = {t.name.casefold(): t for t in record.tables}
        added = []
        for table in loaded:
            previous = existing.get(table.name.casefold())
            entry = TableRecord(
                table_id=previous.table_id if previous else str(uuid.uuid4()),
                name=table.name,
                row_count=table.row_count,
                column_count=table.column_count,
            )
            existing[table.name.casefold()] = entry
            added.append(entry)
        record.tables = sorted(existing.values(), key=lambda t: t.name)
        self.store.save(record)
        (self.store.project_dir(record.id) / PROFILE_FILE).unlink(missing_ok=True)
        with session_scope(self.settings.db_url) as session:
            session.execute(delete(GlossaryRow).where(GlossaryRow.project_id == record.id))
        return added

    @contextmanager
    def warehouse(self, project_id: str) -> Iterator[duckdb.DuckDBPyConnection]:
        """The project's warehouse, held under the project's lock (for views and checks)."""
        self.store.get(project_id)
        with project_lock(project_id), self._connect(project_id) as con:
            yield con

    @contextmanager
    def read_only_warehouse(self, project_id: str) -> Iterator[duckdb.DuckDBPyConnection]:
        """The project's warehouse, read-only and sealed, under the project's lock (answers)."""
        self.store.get(project_id)
        with project_lock(project_id), self._connect(project_id, read_only=True) as con:
            yield con

    def _connect(self, project_id: str, read_only: bool = False) -> duckdb.DuckDBPyConnection:
        """Open the project's warehouse with the configured memory and thread limits."""
        return connect(
            self.store.project_dir(project_id),
            read_only=read_only,
            sealed=read_only,
            memory_limit=self.settings.duckdb_memory_limit,
            threads=self.settings.duckdb_threads,
        )

    def _check_capacity(self, record: ProjectRecord, new_tables: list[str]) -> None:
        """Refuse loads that would push the project past the table limit."""
        names = {t.name.casefold() for t in record.tables} | {n.casefold() for n in new_tables}
        if len(names) > self.settings.max_tables_per_project:
            raise InvalidInputError(
                "Too many tables in this project.",
                {"max_tables": self.settings.max_tables_per_project},
            )

    def _copy_limited(self, stream: BinaryIO, path: Path) -> None:
        """Copy an upload to disk, stopping as soon as it passes the size limit."""
        written = 0
        with path.open("wb") as out:
            while chunk := stream.read(CHUNK_BYTES):
                written += len(chunk)
                if written > self.settings.max_upload_bytes:
                    raise PayloadTooLargeError(
                        "The file is larger than the upload limit.",
                        {"max_upload_mb": self.settings.max_upload_mb},
                    )
                out.write(chunk)
