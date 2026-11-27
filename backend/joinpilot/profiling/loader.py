"""Load uploaded CSV and Parquet files into the project's own DuckDB file.

Each project has one DuckDB database (D-001). CSV files are read as text first and
typed column by column, so ids such as `0000012345` keep their leading zeros.
Uploads are untrusted: their width and row count are checked before any table is
created (a few KB of compressed Parquet can hold hundreds of millions of rows), and
error messages name the user's file but never server paths or cell values.
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pyarrow as pa

from joinpilot.errors import InvalidInputError
from joinpilot.profiling.sql import ident

logger = logging.getLogger(__name__)

WAREHOUSE_FILE = "warehouse.duckdb"
SUPPORTED_SUFFIXES = {".csv", ".parquet"}
MAX_NAME_LENGTH = 63
MAX_DECIMAL_PRECISION = 38
INTEGER_PATTERN = r"^-?(0|[1-9][0-9]{0,17})$"
DECIMAL_PATTERN = r"^-?[0-9]+\.[0-9]{1,6}$"
DATE_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
DELIMITER_HINTS = (",", ";", "\t", "|")


@dataclass(frozen=True)
class LoadedTable:
    """A table created in the warehouse, with its size."""

    name: str
    row_count: int
    column_count: int


def connect(
    project_dir: Path,
    *,
    read_only: bool = False,
    sealed: bool = False,
    memory_limit: str = "1GB",
    threads: int = 2,
) -> duckdb.DuckDBPyConnection:
    """Open the project's DuckDB file with bounded memory and threads.

    A sealed connection (for answering questions) cannot touch files or the network
    and cannot change its own settings, whatever SQL reaches it.
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    config: dict[str, str | bool | int | float | list[str]] = {
        "memory_limit": memory_limit,
        "threads": threads,
    }
    if sealed:
        config |= {"enable_external_access": False, "lock_configuration": True}
    return duckdb.connect(str(project_dir / WAREHOUSE_FILE), read_only=read_only, config=config)


@contextmanager
def time_limit(con: duckdb.DuckDBPyConnection, seconds: float) -> Iterator[None]:
    """Stop the connection's work once `seconds` have passed.

    After the deadline every running statement is interrupted (checked twice a second),
    so a heavy upload can not keep the server's only worker busy. The interruption is
    reported as a plain-language error.
    """
    stop = threading.Event()

    def watch() -> None:
        if stop.wait(seconds):
            return
        while not stop.is_set():
            con.interrupt()
            stop.wait(0.5)

    watcher = threading.Thread(target=watch, name="joinpilot-time-limit", daemon=True)
    watcher.start()
    try:
        yield
    except duckdb.InterruptException as error:
        raise InvalidInputError(
            f"The data took longer than {seconds:g} seconds to process and was stopped.",
            {"timeout_seconds": seconds},
        ) from error
    finally:
        stop.set()
        watcher.join()


def table_name_from_filename(filename: str) -> str:
    """Turn an uploaded file name into a safe table name, for example `vbak (2).csv` -> `vbak_2`."""
    stem = Path(filename).stem
    name = re.sub(r"[^A-Za-z0-9_]+", "_", stem).strip("_")[:MAX_NAME_LENGTH]
    if not name or not name[0].isalpha():
        name = f"t_{name}"[:MAX_NAME_LENGTH]
    return name


def list_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Names of the base tables in the warehouse, sorted."""
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_type = 'BASE TABLE' ORDER BY table_name"
    ).fetchall()
    return [str(r[0]) for r in rows]


def column_names(con: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    """Column names of a table (or temp table) in order."""
    rows = con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = ? ORDER BY ordinal_position",
        [table],
    ).fetchall()
    return [str(r[0]) for r in rows]


def load_file(
    con: duckdb.DuckDBPyConnection,
    path: Path,
    table: str,
    *,
    display_name: str | None = None,
    max_columns: int = 200,
    max_rows: int = 2_000_000,
) -> LoadedTable:
    """Create (or replace) `table` from a CSV or Parquet file and return its size.

    `display_name` is the file name the user uploaded; it is the only file detail
    that appears in errors.
    """
    shown = display_name or path.name
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise InvalidInputError("Only CSV and Parquet files are supported.", {"file": shown})
    if path.stat().st_size == 0:
        raise InvalidInputError("The file is empty.", {"file": shown})
    try:
        if suffix == ".parquet":
            load_parquet(con, path, table, shown, max_columns, max_rows)
        else:
            load_csv(con, path, table, shown, max_columns, max_rows)
    except duckdb.InterruptException:
        raise
    except duckdb.Error as error:
        logger.warning("could not load %s into %s: %s", suffix, table, type(error).__name__)
        reason = "not a valid Parquet file" if suffix == ".parquet" else "could not parse the CSV"
        raise InvalidInputError(
            "The file could not be read as a table.", {"file": shown, "reason": reason}
        ) from error
    rows = con.execute(f"SELECT COUNT(*) FROM {ident(table)}").fetchone()
    loaded = LoadedTable(table, int(rows[0]) if rows else 0, len(column_names(con, table)))
    logger.info(
        "loaded table %s: %d rows, %d columns", table, loaded.row_count, loaded.column_count
    )
    return loaded


def check_width(columns: list[str], shown: str, max_columns: int) -> None:
    """Refuse files that are too wide to profile, or whose columns were not detected."""
    if len(columns) > max_columns:
        raise InvalidInputError(
            "The file has too many columns.",
            {"file": shown, "columns": len(columns), "max_columns": max_columns},
        )
    if len(columns) == 1 and any(hint in columns[0] for hint in DELIMITER_HINTS):
        raise InvalidInputError(
            "The columns could not be detected; check the delimiter and quoting.", {"file": shown}
        )


def check_rows(rows: int, shown: str, max_rows: int) -> None:
    """Refuse tables with more rows than the server can profile and check in time."""
    if rows > max_rows:
        raise InvalidInputError(
            "The file has too many rows.", {"file": shown, "rows": rows, "max_rows": max_rows}
        )


def load_parquet(
    con: duckdb.DuckDBPyConnection,
    path: Path,
    table: str,
    shown: str,
    max_columns: int,
    max_rows: int,
) -> None:
    """Check the Parquet schema's width and its row count, then copy the file into a table.

    The row count comes from the file's metadata, so nothing is decompressed first. The
    footer's total and the sum of its row groups (what a scan actually reads) are both
    checked, so a file whose footer understates its rows is still refused.
    """
    schema = con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).fetchall()
    check_width([str(r[0]) for r in schema], shown, max_columns)
    counts = con.execute(
        "SELECT (SELECT COALESCE(SUM(num_rows), 0) FROM parquet_file_metadata($1)), "
        "(SELECT COALESCE(SUM(n), 0) FROM (SELECT DISTINCT row_group_id, "
        "row_group_num_rows AS n FROM parquet_metadata($1)))",
        [str(path)],
    ).fetchone()
    check_rows(max(int(c) for c in counts) if counts else 0, shown, max_rows)
    con.execute(
        f"CREATE OR REPLACE TABLE {ident(table)} AS SELECT * FROM read_parquet(?)", [str(path)]
    )


def load_arrow(con: duckdb.DuckDBPyConnection, table: str, data: pa.Table) -> LoadedTable:
    """Create (or replace) `table` from an in-memory Arrow table, such as the sample data."""
    con.register("__jp_arrow", data)
    try:
        con.execute(f"CREATE OR REPLACE TABLE {ident(table)} AS SELECT * FROM __jp_arrow")
    finally:
        con.unregister("__jp_arrow")
    return LoadedTable(table, data.num_rows, data.num_columns)


def infer_csv_type(con: duckdb.DuckDBPyConnection, staging: str, column: str) -> str:
    """Pick BIGINT, DECIMAL, DOUBLE, DATE or VARCHAR for one all-text CSV column.

    A column becomes numeric only if no value has a leading zero, because
    zero-padded ids are text in every ERP system. Decimal precision comes from the
    data; numbers too long for DECIMAL(38) fall back to DOUBLE.
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
               MAX(length(split_part({col}, '.', 2))),
               MAX(length(ltrim(split_part({col}, '.', 1), '-')))
        FROM {ident(staging)}
        """,
        [INTEGER_PATTERN, DECIMAL_PATTERN, DATE_PATTERN],
    ).fetchone()
    assert row is not None
    non_null, integers, decimals, dates, scale, int_digits = (int(v or 0) for v in row)
    if non_null == 0:
        return "VARCHAR"
    if integers == non_null:
        return "BIGINT"
    if integers + decimals == non_null:
        scale = max(scale, 1)
        precision = max(int_digits + scale, scale + 1)
        return f"DECIMAL({precision}, {scale})" if precision <= MAX_DECIMAL_PRECISION else "DOUBLE"
    if dates == non_null:
        return "DATE"
    return "VARCHAR"


def load_csv(
    con: duckdb.DuckDBPyConnection,
    path: Path,
    table: str,
    shown: str,
    max_columns: int,
    max_rows: int,
) -> None:
    """Read a CSV as text, check its width, then cast each column to its inferred type."""
    staging = f"__staging_{table}"
    con.execute(
        f"CREATE OR REPLACE TEMP TABLE {ident(staging)} AS "
        "SELECT * FROM read_csv(?, all_varchar = true, header = true)",
        [str(path)],
    )
    try:
        columns = column_names(con, staging)
        check_width(columns, shown, max_columns)
        rows = con.execute(f"SELECT COUNT(*) FROM {ident(staging)}").fetchone()
        check_rows(int(rows[0]) if rows else 0, shown, max_rows)
        casts = ", ".join(
            f"CAST({ident(c)} AS {infer_csv_type(con, staging, c)}) AS {ident(c)}" for c in columns
        )
        con.execute(
            f"CREATE OR REPLACE TABLE {ident(table)} AS SELECT {casts} FROM {ident(staging)}"
        )
    finally:
        con.execute(f"DROP TABLE IF EXISTS {ident(staging)}")
