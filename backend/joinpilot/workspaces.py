"""Private workspaces without login (D-037).

The console makes a random workspace id once per browser and sends it with every
request. Projects belong to one workspace, and the API serves a project, its runs and
its answers only to that workspace. The id works like a long unguessable link: it keeps
visitors of the public demo apart, but it is not an account.

Calls without an id (the MCP server, scripts, tests) use the `local` workspace. The
`demo` workspace holds the preloaded sample project, which every workspace can read.
"""

from __future__ import annotations

import re

from joinpilot.errors import InvalidInputError

HEADER = "X-Workspace"
QUERY = "workspace"
LOCAL = "local"
DEMO = "demo"
# Where the demo project is built; it moves to DEMO only once its run has completed
DEMO_STAGING = "demo-staging"
# At least 16 characters, so the reserved names above can never be sent
_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,64}")


def parse_workspace(value: str | None) -> str:
    """The workspace a request belongs to: its id, or `local` when none is sent."""
    if not value:
        return LOCAL
    if not _PATTERN.fullmatch(value):
        raise InvalidInputError(
            "The workspace id must be 16 to 64 letters, digits, '-' or '_'.",
            {"header": HEADER},
        )
    return value


def visible_workspaces(workspace: str) -> list[str]:
    """The workspaces whose projects a workspace can see: its own and the demo."""
    return [workspace] if workspace == DEMO else [workspace, DEMO]
