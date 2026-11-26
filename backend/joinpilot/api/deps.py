"""FastAPI dependencies: build services from the app's settings."""

from __future__ import annotations

from uuid import UUID

from fastapi import Request
from fastapi.concurrency import run_in_threadpool

from joinpilot.config import Settings
from joinpilot.glossary.service import GlossaryService
from joinpilot.jobs.queue import JobQueue
from joinpilot.services.projects import ProjectService
from joinpilot.services.questions import QuestionService
from joinpilot.services.runs import RunService
from joinpilot.workspaces import HEADER, QUERY, parse_workspace


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


def get_glossary_service(request: Request) -> GlossaryService:
    """A glossary service bound to the app's settings."""
    return GlossaryService(get_settings_from_app(request))


def get_question_service(request: Request) -> QuestionService:
    """A question service that reads models through the run service."""
    return QuestionService(get_settings_from_app(request), get_run_service(request))


def get_workspace(request: Request) -> str:
    """The caller's workspace, from the X-Workspace header (or `workspace` query, for links)."""
    return parse_workspace(request.headers.get(HEADER) or request.query_params.get(QUERY))


# POST endpoints that only read: asking a question changes nothing in the project.
READ_ONLY_POSTS = frozenset({"ask"})


async def guard_project_access(request: Request) -> None:
    """Refuse a project or run that belongs to another workspace (D-037).

    Runs on every route with a `project_id` or `run_id`; changes to the shared demo
    project are refused, reading it is allowed.
    """
    params = request.path_params
    key = "project_id" if "project_id" in params else "run_id" if "run_id" in params else None
    if key is None:
        return
    try:
        UUID(str(params[key]))
    except ValueError:
        return  # not an id at all: the endpoint answers with its own 422
    workspace = get_workspace(request)
    route = request.scope.get("route")
    write = request.method != "GET" and getattr(route, "name", "") not in READ_ONLY_POSTS
    projects = get_project_service(request)
    if "project_id" in params:
        project_id = str(params["project_id"])
    else:
        run = await run_in_threadpool(get_run_service(request).get, str(params["run_id"]))
        project_id = run.project_id
    await run_in_threadpool(projects.check_access, project_id, workspace, write)
