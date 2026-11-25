"""Where run state is saved between steps, so a paused run can resume in another process.

Postgres in Docker and production (LangGraph's PostgresSaver); a local SQLite file
otherwise. Both create their own tables on first use.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.sqlite import SqliteSaver

from joinpilot.config import Settings


def psycopg_url(sqlalchemy_url: str) -> str:
    """psycopg wants `postgresql://`, SQLAlchemy uses `postgresql+psycopg://`."""
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://", 1)


@contextmanager
def open_checkpointer(settings: Settings) -> Iterator[BaseCheckpointSaver[Any]]:
    """A ready checkpointer for the configured database, closed when the block ends."""
    url = settings.db_url
    if url.startswith("postgresql"):
        with PostgresSaver.from_conn_string(psycopg_url(url)) as saver:
            saver.setup()
            yield saver
        return
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.data_dir / "checkpoints.db", check_same_thread=False)
    try:
        sqlite_saver = SqliteSaver(connection)
        sqlite_saver.setup()
        yield sqlite_saver
    finally:
        connection.close()
