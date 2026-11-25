# AGENTS.md

Instructions for AI coding agents (Codex, Cursor, Copilot and others) working on JoinPilot.

CLAUDE.md is the single source of truth for this repository. Read it, then the rules in `.claude/rules/`, before changing code. The essentials:

- Work one task at a time from `docs/PLAN.md`. One task = one small conventional commit with passing checks.
- Synthetic and public data only. Never use real client or employer data.
- `data/gold/` is read only by `eval/` scripts.
- LLM-generated SQL must pass the sqlglot guard in `backend/joinpilot/sqlgen/guard.py`.
- API contract changes update `docs/contract.md`, the backend schemas, the web types and the fixtures together.
- Secrets live only in `.env`. Tests run offline with the fake LLM provider.
