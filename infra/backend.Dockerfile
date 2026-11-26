# syntax=docker/dockerfile:1.7
# JoinPilot backend: the API, with the arq worker running in-process when JOBS_MODE=arq
# (D-022). The same image runs a standalone worker or the MCP server by changing the
# command:  arq joinpilot.jobs.worker.WorkerSettings   |   joinpilot-mcp
#   docker build -f infra/backend.Dockerfile -t joinpilot-api .

FROM ghcr.io/astral-sh/uv:0.13.7 AS uv

FROM python:3.12-slim-trixie AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1
WORKDIR /app
# Dependencies first, so code changes reuse the cached layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/joinpilot ./backend/joinpilot
RUN uv sync --locked --no-dev --no-editable

FROM python:3.12-slim-trixie
RUN useradd --create-home --uid 10001 joinpilot && mkdir /data && chown joinpilot /data
WORKDIR /app
COPY --from=build --chown=joinpilot /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    PORT=8000
USER joinpilot
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=4)"
# Forwarded headers are read by the rate limiter only, from trusted hops (LIMITS__FORWARDED_HOPS).
CMD ["sh", "-c", "exec uvicorn joinpilot.api.main:app --host 0.0.0.0 --port \"$PORT\" --no-proxy-headers"]
