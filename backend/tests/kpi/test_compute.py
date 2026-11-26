from datetime import date

import duckdb

from joinpilot.kpi.compute import compute_metrics, json_value
from joinpilot.kpi.metrics import MetricDef


def metric(sql: str, metric_id: str = "m") -> MetricDef:
    return MetricDef(
        metric_id=metric_id,
        title="A metric",
        description="",
        view="v",
        sql=sql,
        chart="bar",
        x="k",
        y=["total"],
        requested=True,
    )


def warehouse() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("CREATE TABLE raw AS SELECT range % 3 AS k, range * 1.25 AS amount FROM range(9)")
    con.execute("CREATE SCHEMA model")
    con.execute(
        "CREATE VIEW model.v AS SELECT k, CAST(amount AS DECIMAL(10,2)) AS amount, "
        "DATE '2026-01-01' AS day FROM raw"
    )
    return con


def test_metrics_return_json_ready_rows_up_to_the_limit() -> None:
    sql = "SELECT k, SUM(amount) AS total, MIN(day) AS first FROM model.v GROUP BY k ORDER BY k"
    [result] = compute_metrics(warehouse(), [metric(sql)], max_rows=2)
    assert result.status == "computed"
    assert result.data == [
        {"k": 0, "total": 11.25, "first": "2026-01-01"},
        {"k": 1, "total": 15.0, "first": "2026-01-01"},
    ]


def test_unsafe_or_broken_metrics_fail_alone() -> None:
    good = metric("SELECT COUNT(*) AS total FROM model.v", "good")
    raw = metric("SELECT COUNT(*) AS total FROM raw", "outside_the_model")
    bad = metric("SELECT nope FROM model.v", "unknown_column")
    division = metric("SELECT CAST('x' AS INTEGER) AS total FROM model.v", "runtime_error")
    results = {r.metric_id: r for r in compute_metrics(warehouse(), [good, raw, bad, division], 10)}
    assert results["good"].status == "computed"
    for name in ("outside_the_model", "unknown_column", "runtime_error"):
        assert results[name].status == "failed" and results[name].data == []
        assert results[name].message and "could not be computed" in results[name].message


def test_json_values() -> None:
    assert json_value(date(2026, 6, 30)) == "2026-06-30"
    assert json_value("x") == "x"
