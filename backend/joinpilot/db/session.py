"""Database engine, sessions and migrations."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from joinpilot.config import get_settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@lru_cache(maxsize=8)
def get_engine(url: str) -> Engine:
    """One pooled engine per database URL (SQLite gets foreign keys switched on)."""
    if url.startswith("sqlite"):
        database = url.split("///", 1)[-1]
        if database and database != ":memory:":
            Path(database).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False})
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
        return engine
    settings = get_settings()
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )


@contextmanager
def session_scope(url: str) -> Iterator[Session]:
    """A session that commits on success and rolls back on error."""
    factory = sessionmaker(get_engine(url), expire_on_commit=False)
    with factory() as session, session.begin():
        yield session


@lru_cache(maxsize=8)
def ensure_migrated(url: str) -> None:
    """Migrate a database once per process; later calls for the same URL do nothing."""
    migrate(url)


def migrate(url: str) -> None:
    """Bring the database schema up to the latest Alembic revision."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with get_engine(url).begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
