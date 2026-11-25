"""The migration and the models must describe the same schema, on SQLite and Postgres."""

import os
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from joinpilot.db.models import Base
from joinpilot.db.session import get_engine, migrate


def check_schema(url: str) -> None:
    migrate(url)
    engine = get_engine(url)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []
    tables = set(inspect(engine).get_table_names())
    assert {"projects", "project_tables", "runs", "proposals", "llm_calls"} <= tables


def test_migrations_match_the_models_on_sqlite(tmp_path: Path) -> None:
    check_schema(f"sqlite:///{tmp_path / 'app.db'}")


def test_migrating_twice_is_harmless(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'app.db'}"
    migrate(url)
    migrate(url)


@pytest.mark.integration
def test_migrations_match_the_models_on_postgres() -> None:
    url = os.environ.get(
        "TEST_DATABASE_URL", "postgresql+psycopg://joinpilot:joinpilot@localhost:5432/joinpilot"
    )
    check_schema(url)
