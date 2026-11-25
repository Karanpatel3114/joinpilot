from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from joinpilot.api.main import create_app
from joinpilot.config import Settings


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = Settings(_env_file=None, data_dir=tmp_path, max_upload_mb=0.01)
    return TestClient(create_app(settings))
