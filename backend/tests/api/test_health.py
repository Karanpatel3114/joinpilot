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


def test_unexpected_errors_return_the_contract_error_shape() -> None:
    app = create_app(Settings(_env_file=None))

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    response = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in response.text
