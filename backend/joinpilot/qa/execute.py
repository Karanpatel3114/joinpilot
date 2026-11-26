"""Run a guarded answer query read-only, with a row limit and a timeout.

The limit is written into the query (one more row than shown, to tell whether the
answer was cut), so DuckDB never builds a huge result. A timer interrupts the
connection when the query runs too long.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

import duckdb
import sqlglot
from sqlglot import exp

from joinpilot.errors import JoinPilotError
from joinpilot.kpi.compute import json_value

logger = logging.getLogger(__name__)


class QueryTimeoutError(JoinPilotError):
    """The answer query ran longer than QA__TIMEOUT_SECONDS."""

    code = "TIMEOUT"
    http_status = 408


class QueryFailedError(JoinPilotError):
    """The answer query passed the guard but the database could not run it."""

    code = "QUERY_FAILED"
    http_status = 422


@dataclass(frozen=True)
class Result:
    """An answer's rows (at most the limit), their columns and whether more existed."""

    columns: list[str]
    rows: list[dict[str, Any]]
    truncated: bool
    elapsed_ms: float


def with_limit(sql: str, limit: int) -> str:
    """The query with LIMIT at most `limit + 1`, keeping a smaller LIMIT it already has."""
    tree = sqlglot.parse_one(sql, read="duckdb")
    if not isinstance(tree, exp.Query):
        raise QueryFailedError("Only queries can be answered.")
    current = tree.args.get("limit")
    expression = current.expression if isinstance(current, exp.Limit) else None
    if isinstance(expression, exp.Literal) and expression.is_int and int(expression.name) <= limit:
        return tree.sql(dialect="duckdb")
    return tree.limit(limit + 1).sql(dialect="duckdb")


def run_query(
    con: duckdb.DuckDBPyConnection, sql: str, limit: int, timeout_seconds: float
) -> Result:
    """Run a guarded query and return at most `limit` rows as JSON-ready records."""
    started = time.perf_counter()
    timer = threading.Timer(timeout_seconds, con.interrupt)
    timer.start()
    try:
        cursor = con.execute(with_limit(sql, limit))
        columns = [d[0] for d in cursor.description or []]
        rows = cursor.fetchall()
    except duckdb.InterruptException as error:
        raise QueryTimeoutError(
            f"The query took longer than {timeout_seconds:g} seconds and was stopped."
        ) from error
    except duckdb.Error as error:
        raise QueryFailedError(
            f"The database could not run the query ({type(error).__name__})."
        ) from error
    finally:
        timer.cancel()
    elapsed = (time.perf_counter() - started) * 1000
    logger.info("answer query: %d rows in %.0f ms", min(len(rows), limit), elapsed)
    return Result(
        columns=columns,
        rows=[dict(zip(columns, map(json_value, row), strict=True)) for row in rows[:limit]],
        truncated=len(rows) > limit,
        elapsed_ms=round(elapsed, 1),
    )
