---
name: verify
description: Run every relevant check (lint, format, type checks and tests) for the parts of the JoinPilot repo that changed, and report a clear pass or fail. Use this before every commit, after finishing any code change, and whenever the owner asks "does it work", "run the tests" or "check everything".
---

# Verify

Claude Code runs a skill named `verify` right before each commit. This is that skill.

## What to run

Look at `git status` and `git diff --stat` to see what changed, then run the matching checks.

**Backend** (changes in `backend/`, `eval/`, `mcp/`, `pyproject.toml` or `uv.lock`):
```
uv run ruff check .
uv run ruff format --check .
uv run mypy backend/joinpilot
uv run pytest -q
```

**Web** (changes in `web/`):
```
cd web && npm run lint && npm run typecheck && npm test -- --run
```

**Contract** (changes in docs/contract.md, `backend/joinpilot/api/schemas.py`, `web/src/types/api.ts` or fixtures): also run `uv run pytest -q backend/tests/api/test_contract.py`.

Early in M0 some tools won't exist yet. Run whatever is set up, and say which checks were skipped and why.

## Rules
- Report each check as pass or fail, with the key error lines for failures.
- Never mark a run as passing if anything failed. Never skip, delete, `xfail` or loosen a test to get green.
- If a fix is needed, make it, then run the full set again.
- Finish with one line: `VERIFY: PASS` or `VERIFY: FAIL (<which checks>)`.
