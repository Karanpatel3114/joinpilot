from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from joinpilot.profiling.loader import connect


@pytest.fixture
def con(tmp_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = connect(tmp_path / "project")
    yield connection
    connection.close()
