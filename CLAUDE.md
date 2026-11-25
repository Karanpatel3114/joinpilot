# JoinPilot

Project memory for Claude Code. Read this at the start of every session.

## What we are building (plain language first)

JoinPilot takes raw ERP-style tables plus a business requirement written in plain English, and turns them into a tested data model. It profiles the tables, proposes how they should be joined (with the numbers that prove it), generates SQL views, runs automated checks like a system integration test, and waits for a person to approve. Then it builds a KPI dashboard and answers business questions in plain English.

Technically: a FastAPI backend with a LangGraph agent, DuckDB for profiling and a sandboxed warehouse, Postgres with pgvector for app state and glossary search, Redis background jobs, a React console, and an MCP server so other AI tools can use JoinPilot.

Owner: Karan Patel. This is a portfolio project for AI, data and software engineering roles. It productizes work the owner did by hand on a client analytics engagement. Never use any real client or employer data, names, schemas or business logic.

- Spec: @docs/SPEC.md
- Plan and task list: docs/PLAN.md (read it at the start of each session)
- API contract: docs/contract.md
- Dataset spec: docs/data-model.md
- Evaluation plan: docs/eval-plan.md
- Decision log: docs/decisions.md
- Owner's daily workflow: docs/WORKFLOW.md

## How to work here

1. Work on one task at a time from docs/PLAN.md, in order. Use the `next-task` skill.
2. Plan before you code: say which files change, which tests you add, and the commit message. For tasks that touch the API contract, SQL safety, data/gold or the architecture, wait for the owner's OK on the plan.
3. Explain every change in plain language first, then the technical detail. The owner reviews all code and must be able to explain it in an interview.
4. Keep it simple: the smallest change that completes the task. No speculative features or abstractions.
5. One task = one commit. Run the `verify` skill before every commit, then use `commit-step`.
6. Record every design choice that had real alternatives in docs/decisions.md.
7. If a task looks bigger than about 300 changed lines (excluding lockfiles and fixtures), propose a split in PLAN.md before starting.

## Non-negotiables

- Synthetic and public data only (see .claude/rules/data-and-eval.md).
- Gold answers in data/gold/ are for eval/ scripts only. The app, the agent and prompts never read them. Do not open them yourself outside the data milestone (M1).
- LLM-generated SQL is untrusted and must pass the guard (see .claude/rules/sql-safety.md).
- The LLM never invents joins. It ranks and explains the candidates that profiling produced, citing evidence.
- No view is created until a person approves the joins.
- Secrets live only in .env, which is never committed. Keep .env.example complete.
- Tests run offline with the fake LLM provider. The full backend suite stays under 60 seconds.
- API contract changes use the `contract-sync` skill: the contract doc, Pydantic schemas, TypeScript types and fixtures change in the same commit.

## Repo map

```
backend/joinpilot/  Python package: api, services (the one service layer), agent, profiling, joins, sqlgen, checks, kpi, qa, llm, db, jobs, synth, config
backend/tests/      pytest, one test file per module
web/                React + TypeScript + Vite + Tailwind console
mcp/                MCP server exposing JoinPilot tools
shared/fixtures/     example API responses used by the mock API and web tests
data/               generated/ (gitignored), gold/ (committed, small), benchmarks/ (each with its license)
eval/               evaluation scripts; results/ is written by the run-eval skill
infra/              docker-compose, Dockerfiles, deploy notes
docs/               spec, plan, contract, data model, eval plan, decisions, workflow
.claude/            rules, skills, subagents, settings
```

## Commands

Fill these in as each tool is set up in M0, and keep them accurate afterwards.

- Backend setup: `uv sync`
- Backend checks: `uv run ruff check . && uv run ruff format --check . && uv run mypy backend/joinpilot eval && uv run pytest -q`
- Web setup: `cd web && npm install`
- Web checks: `cd web && npm run lint && npm run typecheck && npm test -- --run`
- Run locally: `docker compose -f infra/docker-compose.yml up -d`, then `uv run uvicorn joinpilot.api.main:app --reload` and `cd web && npm run dev`
- Generate data: `uv run python -m joinpilot.synth.generate --seed 1 --size S --naming sap --out data/generated/erp_s1_sap`
- Regenerate gold (M1 only): `uv run python -m joinpilot.synth.splits --gold data/gold` and `uv run python -m joinpilot.synth.tpch --sf 0.1 --gold data/gold`
- Integration tests (Postgres, Redis, network): `uv run pytest -m integration`
- Evaluation: `uv run python -m eval.run_all --split dev`

## Git

Details are in .claude/rules/git-commits.md. In short: small conventional commits, one per task, checks green, the owner approves each commit, push after every commit, one branch and pull request per milestone, merge without squashing, never force-push or rewrite history, no Co-Authored-By trailers.

## Skills and subagents

- Skills: `next-task`, `verify`, `commit-step`, `contract-sync`, `run-eval`, `erp-data`.
- Subagents: `code-reviewer` (before each milestone pull request), `test-writer` (new modules), `sql-auditor` (any change to sqlgen, checks, qa or mcp), `eval-analyst` (after every evaluation run).
