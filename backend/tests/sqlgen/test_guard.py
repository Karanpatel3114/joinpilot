import duckdb
import pytest

from joinpilot.sqlgen.guard import (
    Catalog,
    UnknownIdentifierError,
    UnsafeSQLError,
    catalog_from_connection,
    guard_sql,
)


@pytest.fixture
def catalog() -> Catalog:
    c = Catalog()
    c.add("main", "KNA1", {"KUNNR": "VARCHAR", "NAME1": "VARCHAR"})
    c.add(
        "main",
        "BSID",
        {"KUNNR": "VARCHAR", "DMBTR": "DECIMAL", "ZFBDT": "DATE", "ZBD1T": "INTEGER"},
    )
    c.add("model", "v_bsid", {"KUNNR": "VARCHAR", "DMBTR": "DECIMAL"})
    return c


ALLOWED = [
    "SELECT KUNNR, NAME1 FROM KNA1",
    "select k.NAME1, sum(b.DMBTR) as total from BSID b join KNA1 k "
    "on lpad(b.KUNNR, 10, '0') = k.KUNNR group by 1 order by 2 desc limit 5",
    "WITH t AS (SELECT KUNNR FROM KNA1) SELECT count(*) FROM t",
    "SELECT KUNNR FROM KNA1 UNION SELECT KUNNR FROM BSID",
    "SELECT CASE WHEN date_diff('day', ZFBDT + ZBD1T * INTERVAL 1 DAY, DATE '2026-06-30') > 90 "
    "THEN '90+' ELSE 'other' END AS bucket, sum(DMBTR) FROM BSID GROUP BY 1",
    "SELECT * FROM model.v_bsid",
    "SELECT kna1.kunnr FROM kna1",
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_ordinary_analytics_queries_are_allowed(sql: str, catalog: Catalog) -> None:
    assert guard_sql(sql, catalog).upper().startswith(("SELECT", "WITH"))


@pytest.mark.parametrize(
    ("sql", "code"),
    [
        ("SELECT 1; DROP TABLE KNA1", "UNSAFE_SQL"),
        ("DELETE FROM KNA1", "UNSAFE_SQL"),
        ("ATTACH 'other.db'", "UNSAFE_SQL"),
        ("SELECT * FROM read_csv('/etc/passwd')", "UNSAFE_SQL"),
        ("SELECT * FROM KNA1, read_parquet('s3://bucket/x.parquet')", "UNSAFE_SQL"),
        ("SELECT getenv('HOME')", "UNSAFE_SQL"),
        ("SELECT * FROM 'data.csv'", "UNKNOWN_IDENTIFIER"),
        ("SELECT nope FROM KNA1", "UNKNOWN_IDENTIFIER"),
        ("SELECT * FROM information_schema.tables", "UNKNOWN_IDENTIFIER"),
        ("SELECT FROM WHERE (((", "UNSAFE_SQL"),
    ],
)
def test_unsafe_statements_are_refused_with_a_reason(sql: str, code: str, catalog: Catalog) -> None:
    with pytest.raises(UnsafeSQLError) as error:
        guard_sql(sql, catalog)
    assert error.value.code == code


def test_views_must_replace_inside_the_sandbox_schema(catalog: Catalog) -> None:
    ok = guard_sql(
        "CREATE OR REPLACE VIEW model.v AS SELECT KUNNR FROM KNA1", catalog, "create_view"
    )
    assert ok.startswith("CREATE OR REPLACE VIEW model.v")
    for sql in (
        "CREATE VIEW model.v AS SELECT KUNNR FROM KNA1",
        "CREATE OR REPLACE VIEW main.v AS SELECT KUNNR FROM KNA1",
        "CREATE OR REPLACE TABLE model.v AS SELECT KUNNR FROM KNA1",
        "SELECT KUNNR FROM KNA1",
    ):
        with pytest.raises(UnsafeSQLError):
            guard_sql(sql, catalog, "create_view")


def test_select_mode_refuses_ddl(catalog: Catalog) -> None:
    with pytest.raises(UnsafeSQLError):
        guard_sql("CREATE OR REPLACE VIEW model.v AS SELECT KUNNR FROM KNA1", catalog)


def test_the_catalog_comes_from_the_warehouse() -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE KNA1 (KUNNR VARCHAR, NAME1 VARCHAR)")
    con.execute("CREATE SCHEMA model")
    con.execute("CREATE VIEW model.v AS SELECT KUNNR FROM KNA1")
    catalog = catalog_from_connection(con, ("main", "model"))
    assert catalog.schemas == {
        "main": {"KNA1": {"KUNNR": "VARCHAR", "NAME1": "VARCHAR"}},
        "model": {"v": {"KUNNR": "VARCHAR"}},
    }
    with pytest.raises(UnknownIdentifierError):
        guard_sql("SELECT * FROM secret", catalog)
