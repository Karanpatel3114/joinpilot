"""Alembic environment: runs migrations on the connection passed in by `migrate()`,
or on DATABASE_URL when run from the command line."""

from __future__ import annotations

from alembic import context
from sqlalchemy import Connection

from joinpilot.config import get_settings
from joinpilot.db.models import Base

target_metadata = Base.metadata


def owned_by_us(name: str | None, type_: str, parent_names: object) -> bool:
    """Ignore tables Alembic does not own, such as LangGraph's checkpoint tables."""
    return type_ != "table" or name in target_metadata.tables


def run(connection: Connection) -> None:
    """Run the migrations on one connection (batch mode for SQLite's limited ALTER)."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
        include_name=owned_by_us,
    )
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:
    run(connection)
else:
    from joinpilot.db.session import get_engine

    with get_engine(get_settings().db_url).begin() as conn:
        run(conn)
