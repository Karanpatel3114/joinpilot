---
paths:
  - "backend/**/*.py"
  - "eval/**/*.py"
  - "mcp/**/*.py"
---
# Python rules

- Python 3.12, managed with uv. Add dependencies with `uv add`, never by hand-editing versions without a reason.
- Type hints on every function. mypy must pass on `backend/joinpilot`. Prefer precise types to `Any`.
- ruff for linting and formatting. Keep imports sorted.
- Pydantic v2 models for every input and output that crosses a boundary (API, agent state, LLM output, job payloads).
- Settings come from `joinpilot/config.py` (pydantic-settings). Every threshold and tunable number lives there, never inline.
- Use `pathlib`, never string paths. Code must run on macOS and Linux.
- Use the `logging` module, never `print`, in package code.
- FastAPI endpoints are async. Blocking DuckDB or CPU work runs in a worker thread or a background job.
- Small functions with docstrings on public ones. Raise clear domain errors from `joinpilot/errors.py`; the API maps them to HTTP responses.
- One service layer: the API, the worker, the MCP server and the evaluation all call the same functions in the package, so reported numbers come from the code that runs.

## Tests
- pytest, one test file per module, mirroring the package path (for example `backend/tests/profiling/test_keys.py`).
- Offline by default: no network, and LLM calls use `joinpilot.llm.fake.FakeProvider`.
- Use small synthetic fixtures. Tests that need Postgres or Redis are marked `@pytest.mark.integration` and excluded from the default run.
- The default suite runs in under 60 seconds.
