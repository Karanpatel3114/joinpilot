import duckdb
import pytest

from joinpilot.qa.execute import QueryFailedError, QueryTimeoutError, run_query, with_limit


def test_the_limit_is_written_into_the_query() -> None:
    assert with_limit("SELECT 1 AS x", 10).endswith("LIMIT 11")
    assert with_limit("SELECT 1 AS x LIMIT 5", 10).endswith("LIMIT 5")
    assert with_limit("SELECT 1 AS x LIMIT 50", 10).endswith("LIMIT 11")
    assert "LIMIT 11" in with_limit("SELECT 1 AS x UNION ALL SELECT 2", 10)


def test_answers_are_cut_at_the_limit_and_say_so() -> None:
    con = duckdb.connect()
    result = run_query(con, "SELECT range AS n, range * 1.5 AS v FROM range(10) ORDER BY n", 3, 5)
    assert result.columns == ["n", "v"]
    assert result.rows == [{"n": 0, "v": 0.0}, {"n": 1, "v": 1.5}, {"n": 2, "v": 3.0}]
    assert result.truncated
    assert not run_query(con, "SELECT 1 AS n", 3, 5).truncated


def test_a_slow_query_is_stopped() -> None:
    con = duckdb.connect()
    slow = (
        "SELECT COUNT(*) AS n FROM range(100000000) a, range(100000) b WHERE a.range % 7 = b.range"
    )
    with pytest.raises(QueryTimeoutError, match=r"longer than 0\.2 seconds"):
        run_query(con, slow, 10, 0.2)
    assert run_query(con, "SELECT 1 AS n", 10, 5).rows == [{"n": 1}], "the connection still works"


def test_a_query_the_database_cannot_run_fails_cleanly() -> None:
    with pytest.raises(QueryFailedError, match="ConversionException"):
        run_query(duckdb.connect(), "SELECT CAST('x' AS INTEGER) AS n", 10, 5)
