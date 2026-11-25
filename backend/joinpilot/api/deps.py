"""FastAPI dependencies: build services from the app's settings."""

from __future__ import annotations

from fastapi import Request

from joinpilot.config import Settings
from joinpilot.services.projects import ProjectService


def get_settings_from_app(request: Request) -> Settings:
    """The settings the app was created with (tests pass their own)."""
    settings: Settings = request.app.state.settings
    return settings


def get_project_service(request: Request) -> ProjectService:
    """A project service bound to the app's settings."""
    return ProjectService(get_settings_from_app(request))
