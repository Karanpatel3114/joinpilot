from fastapi.testclient import TestClient

from joinpilot import __version__
from joinpilot.api.main import create_app
from joinpilot.config import Settings


def make_client() -> TestClient:
    return TestClient(create_app(Settings(_env_file=None)))


def test_health_returns_ok_and_version() -> None:
    response = make_client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_cors_allows_only_configured_origins() -> None:
    client = make_client()
    allowed = client.get("/health", headers={"Origin": "http://localhost:5173"})
    blocked = client.get("/health", headers={"Origin": "https://evil.example"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in blocked.headers


def test_unknown_route_returns_404() -> None:
    assert make_client().get("/nope").status_code == 404
