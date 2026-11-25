"""FastAPI application factory."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from joinpilot import __version__
from joinpilot.api.errors import install_error_handlers
from joinpilot.api.schemas import HealthResponse
from joinpilot.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API with CORS limited to the configured origins."""
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)
    app = FastAPI(title="JoinPilot API", version=__version__)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    install_error_handlers(app)

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Liveness check used by Docker, the console and uptime pings."""
        return HealthResponse(status="ok", version=__version__)

    return app


app = create_app()
