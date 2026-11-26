"""Compute dashboard metrics on the generated views.

Every metric's SQL goes through the guard against the model schema only, runs on
the project's warehouse and returns at most a configured number of rows. A metric
that fails is reported with a reason; the others still show.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

import duckdb

from joinpilot.errors import JoinPilotError
from joinpilot.kpi.metrics import MetricDef
from joinpilot.sqlgen.guard import SANDBOX_SCHEMA, catalog_from_connection, guard_sql

logger = logging.getLogger(__name__)


class Metric(MetricDef):
    """A metric with its computed rows."""

    data: list[dict[str, Any]]
    status: Literal["computed", "failed"]
    message: str | None = None


def json_value(value: Any) -> Any:
    """Money becomes a number for charts; dates become ISO text."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


def compute_metrics(
    con: duckdb.DuckDBPyConnection, metrics: list[MetricDef], max_rows: int
) -> list[Metric]:
    """Run each metric's guarded SQL and keep its rows as JSON-ready records."""
    catalog = catalog_from_connection(con, (SANDBOX_SCHEMA,))
    computed = []
    for metric in metrics:
        started = time.perf_counter()
        try:
            cursor = con.execute(guard_sql(metric.sql, catalog))
            names = [d[0] for d in cursor.description or []]
            rows = cursor.fetchmany(max_rows)
        except (JoinPilotError, duckdb.Error) as error:
            logger.warning("metric %s failed: %s", metric.metric_id, type(error).__name__)
            computed.append(
                Metric(
                    **metric.model_dump(),
                    data=[],
                    status="failed",
                    message=f"The metric could not be computed ({type(error).__name__}).",
                )
            )
            continue
        logger.info(
            "metric %s: %d rows in %.0f ms",
            metric.metric_id,
            len(rows),
            (time.perf_counter() - started) * 1000,
        )
        data = [dict(zip(names, map(json_value, row), strict=True)) for row in rows]
        computed.append(Metric(**metric.model_dump(), data=data, status="computed"))
    return computed
