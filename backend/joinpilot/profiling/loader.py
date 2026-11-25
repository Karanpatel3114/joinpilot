"""Load uploaded CSV and Parquet files into the project's own DuckDB file.

Each project has one DuckDB database (D-001). CSV files are read as text first and
typed column by column, so ids such as `0000012345` keep their leading zeros.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import duckdb

from joinpilot.errors import InvalidInputError
from joinpilot.profiling.sql import ident

logger = logging.getLogger(__name__)

WAREHOUSE_FILE = "warehouse.duckdb"
SUPPORTED_SUFFIXES = {".csv", ".parquet"}
MAX_NAME_LENGTH = 63
INTEGER_PATTERN = r"^-?(0|[1-9][0-9]{0,17})$"
DECIMAL_PATTERN = r"^-?[0-9]+\.[0-9]{1,6}$"
DATE_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"


@dataclass(frozen=True)
class LoadedTable:
    name: str
    row_count: int
    column_count: int


def connect(project_dir: Path, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the project's DuckDB file, creating the folder on first use."""
    project_dir.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(project_dir / WAREHOUSE_FILE), read_only=read_only)


def table_name_from_filename(filename: str) -> str:
    """Turn an uploaded file name into a safe table name, for example `vbak (2).csv` -> `vbak_2`."""
    stem = Path(filename).stem
    name = re.sub(r"[^A-Za-z0-9_]+", "_", stem).strip("_")[:MAX_NAME_LENGTH]
    if not name or not name[0].isalpha():
        name = f"t_{name}"[:MAX_NAME_LENGTH]
    return name


def list_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_type = 'BASE TABLE' ORDER BY table_name"
    ).fetchall()
    return [str(r[0]) for r in rows]


def load_file(con: duckdb.DuckDBPyConnection, path: Path, table: str) -> LoadedTable:
    """Create (or replace) `table` from a CSV or Parquet file and return its size."""
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise InvalidInputError("Only CSV and Parquet files are supported.", {"file": path.name})
    try:
        if suffix == ".parquet":
            con.execute(
                f"CREATE OR REPLACE TABLE {ident(table)} AS SELECT * FROM read_parquet(?)",
                [str(path)],
            )
        else:
            load_csv(con, path, table)
    except duckdb.Error as error:
        raise InvalidInputError(
            "The file could not be read as a table.", {"file": path.name, "reason": str(error)}
        ) from error
    rows = con.execute(f"SELECT COUNT(*) FROM {ident(table)}").fetchone()
    columns = con.execute(
        "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = ?", [table]
    ).fetchone()
    loaded = LoadedTable(table, int(rows[0]) if rows else 0, int(columns[0]) if columns else 0)
    logger.info(
        "loaded table %s: %d rows, %d columns", table, loaded.row_count, loaded.column_count
    )
    return loaded


def infer_csv_type(con: duckdb.DuckDBPyConnection, staging: str, column: str) -> str:
    """Pick BIGINT, DECIMAL, DATE or VARCHAR for one all-text CSV column.

    A column becomes numeric only if no value has a leading zero, because
    zero-padded ids are text in every ERP system.
    """
    col = ident(column)
    row = con.execute(
        f"""
        SELECT COUNT({col}),
               COUNT(*) FILTER (WHERE regexp_matches({col}, ?)),
               COUNT(*) FILTER (WHERE regexp_matches({col}, ?)),
               COUNT(*) FILTER (
                   WHERE regexp_matches({col}, ?) AND TRY_CAST({col} AS DATE) IS NOT NULL
               ),
               MAX(length(split_part({col}, '.', 2)))
        FROM {ident(staging)}
        """,
        [INTEGER_PATTERN, DECIMAL_PATTERN, DATE_PATTERN],
    ).fetchone()
    assert row is not None
    non_null, integers, decimals, dates, scale = (int(v or 0) for v in row)
    if non_null == 0:
        return "VARCHAR"
    if integers == non_null:
        return "BIGINT"
    if integers + decimals == non_null:
        return f"DECIMAL(18, {max(scale, 1)})"
    if dates == non_null:
        return "DATE"
    return "VARCHAR"


def load_csv(con: duckdb.DuckDBPyConnection, path: Path, table: str) -> None:
    """Read a CSV as text, then cast each column to its inferred type."""
    staging = f"__staging_{table}"
    con.execute(
        f"CREATE OR REPLACE TEMP TABLE {ident(staging)} AS "
        "SELECT * FROM read_csv(?, all_varchar = true, header = true)",
        [str(path)],
    )
    try:
        columns = [
            str(r[0])
            for r in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = ? ORDER BY ordinal_position",
                [staging],
            ).fetchall()
        ]
        casts = ", ".join(
            f"CAST({ident(c)} AS {infer_csv_type(con, staging, c)}) AS {ident(c)}" for c in columns
        )
        con.execute(
            f"CREATE OR REPLACE TABLE {ident(table)} AS SELECT {casts} FROM {ident(staging)}"
        )
    finally:
        con.execute(f"DROP TABLE IF EXISTS {ident(staging)}")
