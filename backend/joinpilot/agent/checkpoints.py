"""Where run state is saved between steps, so a paused run can resume in another process.

Postgres in Docker and production (LangGraph's PostgresSaver); a local SQLite file
otherwise. Both create their own tables on first use.
"""

from __future__ import annotations

import sqlite3
import threading
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


_SET_UP: set[str] = set()
_SETUP_LOCK = threading.Lock()


def set_up_once(url: str, saver: PostgresSaver | SqliteSaver) -> None:
    """Create the checkpoint tables once per process (concurrent first setups could race)."""
    with _SETUP_LOCK:
        if url not in _SET_UP:
            saver.setup()
            _SET_UP.add(url)


@contextmanager
def open_checkpointer(settings: Settings) -> Iterator[BaseCheckpointSaver[Any]]:
    """A ready checkpointer for the configured database, closed when the block ends."""
    url = settings.db_url
    if url.startswith("postgresql"):
        with PostgresSaver.from_conn_string(psycopg_url(url)) as saver:
            set_up_once(url, saver)
            yield saver
        return
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    path = settings.data_dir / "checkpoints.db"
    connection = sqlite3.connect(path, check_same_thread=False, timeout=30)
    connection.execute("PRAGMA journal_mode=WAL")
    try:
        sqlite_saver = SqliteSaver(connection)
        set_up_once(str(path), sqlite_saver)
        yield sqlite_saver
    finally:
        connection.close()
