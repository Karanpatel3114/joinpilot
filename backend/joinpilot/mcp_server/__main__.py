"""Run JoinPilot's MCP server over stdio: `uv run python -m joinpilot.mcp_server`."""

from __future__ import annotations

import logging
import sys

from joinpilot.config import get_settings
from joinpilot.mcp_server.server import build_server


def main() -> None:
    """Start the server; logs go to stderr because stdout carries the protocol."""
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(message)s")
    build_server(get_settings()).run()


if __name__ == "__main__":
    main()
