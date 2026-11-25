"""FastAPI dependencies: build services from the app's settings."""

from __future__ import annotations

from fastapi import Request

from joinpilot.config import Settings
from joinpilot.jobs.queue import JobQueue
from joinpilot.services.projects import ProjectService
from joinpilot.services.runs import RunService


def get_settings_from_app(request: Request) -> Settings:
    """The settings the app was created with (tests pass their own)."""
    settings: Settings = request.app.state.settings
    return settings


def get_project_service(request: Request) -> ProjectService:
    """A project service bound to the app's settings."""
    return ProjectService(get_settings_from_app(request))


def get_run_service(request: Request) -> RunService:
    """A run service using the app's job queue."""
    jobs: JobQueue = request.app.state.jobs
    return RunService(get_settings_from_app(request), jobs)
