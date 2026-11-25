"""The SQL guard: every statement built from model output or user input passes here
before it runs (.claude/rules/sql-safety.md).

Allowed: exactly one SELECT (WITH and set operations included) or, in view mode, one
CREATE OR REPLACE VIEW inside the sandbox schema. Every function must be on an
allowlist, so file, network and system access (read_csv, glob, getenv, ...) is
impossible, and every table and column must exist in the project's catalog.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, cast

import duckdb
import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError, ParseError
from sqlglot.optimizer.qualify import qualify

from joinpilot.errors import JoinPilotError

Mode = Literal["select", "create_view"]
SANDBOX_SCHEMA = "model"
DIALECT = "duckdb"

# Scalar, aggregate and window functions a model or a question may use. Anything else,
# including every table function, is refused.
ALLOWED_FUNCTIONS = frozenset(
    (
        "abs",
        "any_value",
        "anyvalue",
        "approx_count_distinct",
        "approx_distinct",
        "array_agg",
        "avg",
        "bool_and",
        "bool_or",
        "case",
        "cast",
        "ceil",
        "ceiling",
        "coalesce",
        "concat",
        "concat_ws",
        "count",
        "count_if",
        "countif",
        "current_date",
        "date",
        "date_add",
        "date_diff",
        "date_from_parts",
        "date_part",
        "date_sub",
        "date_trunc",
        "dateadd",
        "datediff",
        "datesub",
        "datetrunc",
        "day",
        "day_of_week",
        "dayofmonth",
        "dayofweek",
        "dayofyear",
        "dense_rank",
        "div",
        "extract",
        "first",
        "first_value",
        "floor",
        "greatest",
        "group_concat",
        "if",
        "ifnull",
        "iif",
        "lag",
        "last",
        "last_value",
        "lead",
        "least",
        "left",
        "length",
        "logical_and",
        "logical_or",
        "lower",
        "lpad",
        "ltrim",
        "make_date",
        "max",
        "median",
        "min",
        "mod",
        "month",
        "nth_value",
        "ntile",
        "nullif",
        "pad",
        "percent_rank",
        "percentile_cont",
        "percentile_disc",
        "quarter",
        "rank",
        "regexp_like",
        "regexp_matches",
        "regexp_replace",
        "replace",
        "right",
        "round",
        "row_number",
        "rpad",
        "rtrim",
        "sign",
        "split_part",
        "sqrt",
        "stddev",
        "stddev_pop",
        "stddev_samp",
        "str_to_date",
        "str_to_time",
        "strftime",
        "string_agg",
        "strptime",
        "substr",
        "substring",
        "sum",
        "time_to_str",
        "time_to_unix",
        "timestamp_trunc",
        "to_date",
        "trim",
        "trunc",
        "try_cast",
        "try_strptime",
        "unix_to_time",
        "upper",
        "var_pop",
        "var_samp",
        "variance",
        "week",
        "year",
        "yearweek",
    )
)


class UnsafeSQLError(JoinPilotError):
    """The statement was refused by the guard."""

    code = "UNSAFE_SQL"
    http_status = 422


class UnknownIdentifierError(UnsafeSQLError):
    """The statement names a table or column that is not in the catalog."""

    code = "UNKNOWN_IDENTIFIER"


@dataclass
class Catalog:
    """Tables and columns a statement may use: {schema: {table: {column: type}}}."""

    schemas: dict[str, dict[str, dict[str, str]]] = field(default_factory=dict)

    def add(self, schema: str, table: str, columns: dict[str, str]) -> None:
        """Allow one table (or view) with its columns."""
        self.schemas.setdefault(schema, {})[table] = dict(columns)


def function_name(node: exp.Func) -> str:
    """Lower-case function name, also for functions sqlglot does not know."""
    if isinstance(node, exp.Anonymous):
        return str(node.name).lower()
    return node.sql_name().lower()


def parse_one_statement(sql: str) -> exp.Expression:
    """Parse with sqlglot and insist on exactly one statement."""
    try:
        statements: list[exp.Expression] = [
            s for s in sqlglot.parse(sql, read=DIALECT) if isinstance(s, exp.Expression)
        ]
    except ParseError as error:
        raise UnsafeSQLError("The SQL could not be parsed.", {"reason": "parse_error"}) from error
    if len(statements) != 1:
        raise UnsafeSQLError(
            "Exactly one SQL statement is allowed.", {"statements": len(statements)}
        )
    return statements[0]


def query_of(statement: exp.Expression, mode: Mode) -> exp.Query:
    """The SELECT to check: the statement itself, or the body of an allowed view."""
    if mode == "select":
        if not isinstance(statement, exp.Query):
            raise UnsafeSQLError("Only SELECT queries are allowed.", {"statement": statement.key})
        return statement
    is_view = (
        isinstance(statement, exp.Create)
        and str(statement.args.get("kind", "")).upper() == "VIEW"
        and statement.args.get("replace")
    )
    if not is_view:
        raise UnsafeSQLError("Only CREATE OR REPLACE VIEW is allowed here.")
    target = statement.this.this if isinstance(statement.this, exp.Schema) else statement.this
    if not isinstance(target, exp.Table) or target.db != SANDBOX_SCHEMA:
        raise UnsafeSQLError(f"Views must be created in the {SANDBOX_SCHEMA} schema.")
    body = statement.expression
    if not isinstance(body, exp.Query):
        raise UnsafeSQLError("A view must be defined by a SELECT query.")
    return body


def check_nodes(query: exp.Query) -> None:
    """Refuse statements hidden inside the query, table functions and unknown functions."""
    for node in query.walk():
        if isinstance(
            node,
            (
                exp.DDL,
                exp.DML,
                exp.Command,
                exp.Pragma,
                exp.Set,
                exp.Copy,
                exp.Attach,
                exp.Detach,
                exp.Install,
                exp.Use,
                exp.Transaction,
            ),
        ):
            raise UnsafeSQLError(
                "The query contains a statement that is not allowed.", {"node": node.key}
            )
        if isinstance(node, exp.Table) and not isinstance(node.this, exp.Identifier):
            raise UnsafeSQLError("Table functions are not allowed.", {"node": node.this.key})
        is_operator = isinstance(node, (exp.Connector, exp.Binary, exp.Unary))
        if (
            isinstance(node, exp.Func)
            and not is_operator
            and function_name(node) not in ALLOWED_FUNCTIONS
        ):
            raise UnsafeSQLError(
                "The query uses a function that is not allowed.", {"function": function_name(node)}
            )


def check_identifiers(query: exp.Query, catalog: Catalog) -> exp.Query:
    """Resolve every table and column against the catalog with sqlglot's qualifier."""
    for table in query.find_all(exp.Table):
        schema = table.db or None
        if schema and schema.casefold() not in {s.casefold() for s in catalog.schemas}:
            raise UnknownIdentifierError("The query uses an unknown schema.", {"schema": schema})
    try:
        qualified = qualify(
            query.copy(),
            schema=cast(dict[str, object], catalog.schemas),
            db="main",
            dialect=DIALECT,
            validate_qualify_columns=True,
        )
    except OptimizeError as error:
        raise UnknownIdentifierError(
            "The query names a table or column that does not exist.", {"reason": str(error)[:200]}
        ) from error
    known = {(s.casefold(), t.casefold()) for s, tables in catalog.schemas.items() for t in tables}
    ctes = {cte.alias.casefold() for cte in qualified.find_all(exp.CTE)}
    for table in qualified.find_all(exp.Table):
        name, schema = table.name.casefold(), (table.db or "main").casefold()
        if name in ctes and not table.db:
            continue
        if (schema, name) not in known:
            raise UnknownIdentifierError("The query uses an unknown table.", {"table": table.name})
    assert isinstance(qualified, exp.Query)
    return qualified


def guard_sql(sql: str, catalog: Catalog, mode: Mode = "select") -> str:
    """Return the statement as safe, normalized DuckDB SQL, or raise UnsafeSQLError."""
    statement = parse_one_statement(sql)
    query = query_of(statement, mode)
    check_nodes(query)
    check_identifiers(query, catalog)
    return statement.sql(dialect=DIALECT)


def catalog_from_connection(con: duckdb.DuckDBPyConnection, schemas: tuple[str, ...]) -> Catalog:
    """The tables and views (with column types) a project's warehouse has in `schemas`."""
    rows = con.execute(
        "SELECT table_schema, table_name, column_name, data_type "
        "FROM information_schema.columns WHERE table_schema IN (SELECT unnest(?)) "
        "ORDER BY table_schema, table_name, ordinal_position",
        [list(schemas)],
    ).fetchall()
    catalog = Catalog()
    for schema, table, column, data_type in rows:
        catalog.schemas.setdefault(str(schema), {}).setdefault(str(table), {})[str(column)] = str(
            data_type
        )
    return catalog
