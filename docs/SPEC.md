# JoinPilot: build spec (v1)

## Problem
Turning a business requirement and raw ERP tables into a trustworthy data model is slow, manual work. Analysts study cryptic tables, guess join keys, write SQL views and test them by hand before anyone can trust a dashboard. Small mistakes, like a wrong key, a join that duplicates rows, or records with no match, silently corrupt the KPIs that leaders use.

## Who it's for
- Analytics engineers and BI developers building models on ERP data.
- Consultants delivering client dashboards on tight timelines.
- Forward deployed and solutions engineers who need a working data model on a new customer's data within days.

## What it does
1. Create a project and upload tables (CSV or Parquet), or load the sample ERP dataset.
2. JoinPilot profiles every column: type, nulls, distinct values, candidate keys, and how much its values overlap with other columns.
3. The user writes the requirement in plain English, for example: "Open receivables by customer and aging bucket, plus 2026 revenue by product group."
4. The agent proposes a join graph. Every join shows its evidence: overlap ratio, key uniqueness, cardinality, any normalization needed (such as stripping leading zeros), and fan-out risk.
5. The user approves, rejects or edits each join.
6. JoinPilot generates SQL views, runs automated SIT checks, repairs failures (up to 2 attempts) and shows the results.
7. A KPI dashboard is generated from metric definitions.
8. The user asks questions in plain English. JoinPilot answers with guarded, read-only SQL and shows the query.
9. Other AI tools, such as Claude Desktop or Claude Code, can use JoinPilot through its MCP server.

## Features by phase
- **MVP (M0–M6):** data generator, profiling, join candidates, agent ranking with evidence, human approval, view generation, SIT checks, evaluation.
- **v1 (M7–M11):** web console, KPI dashboard, question answering, MCP server, Docker, CI/CD, deployment, tracing.
- **Polish (M12):** authentication, demo mode, final evaluation, README and demo video.
- **Stretch (only after v1):** dbt project export, test runs in Snowflake or BigQuery dialects, incremental re-profiling.

## Architecture
```
 web/ React console ──HTTP──▶ FastAPI (api/) ◀── mcp/ MCP server
                                  │
         ┌────────────────────────┼──────────────────────────────┐
         ▼                        ▼                              ▼
   profiling/ (DuckDB)     agent/ (LangGraph)                db/ (Postgres + pgvector)
   joins/ (candidates,     parse requirement → rank joins    projects, runs, proposals,
   scoring)                → interrupt for approval          approvals, glossary,
                           → generate views → SIT checks     LangGraph checkpoints
                           → repair → publish
         │                        │
         ▼                        ▼
   sqlgen/ + guard (sqlglot) → sandbox DuckDB     checks/   kpi/   qa/ (text-to-SQL)
                                  │
                 llm/ provider interface: Gemini · fake (tests) · Ollama (optional)
 jobs/ worker (arq + Redis) runs long agent steps · tracing: Langfuse (optional)
```

## Stack
| Layer | Choice |
|---|---|
| Language | Python 3.12 (uv), TypeScript |
| API | FastAPI, Pydantic v2, pydantic-settings, Uvicorn |
| Agent | LangGraph with the Postgres checkpointer |
| LLM | Google Gemini (free tier) behind a provider interface; fake provider for tests; Ollama optional |
| Profiling and sandbox | DuckDB (one database file per project) |
| SQL parsing and guard | sqlglot |
| App database | Postgres with pgvector (local in Docker; Neon or Supabase in production); SQLAlchemy 2 and Alembic |
| Jobs | arq with Redis (local in Docker; Upstash in production) |
| Web | React 19, Vite, Tailwind CSS, TanStack Query, React Flow, Recharts |
| MCP | Official Python MCP SDK |
| Quality | pytest, Hypothesis, ruff, mypy, Vitest, Testing Library, Playwright |
| Ops | Docker, docker-compose, GitHub Actions, Langfuse |
| Hosting | Web on Vercel; API and worker on Render or Hugging Face Spaces. Check current free-tier limits before M11. |

## Design principles
- **Deterministic first, LLM second.** Profiling and join candidates are pure code. The LLM interprets the requirement, ranks and explains candidates, and drafts SQL, and everything it produces is validated.
- **A person approves** before anything is materialized.
- **One service layer** shared by the API, worker, MCP server and evaluation, so the reported numbers come from the code that runs.
- **Contract-first API**, kept in sync with the `contract-sync` skill.

## Data
A synthetic ERP dataset with SAP-style and friendly naming modes, planted data-quality issues and generator-written gold answers (docs/data-model.md). Plus TPC-H through DuckDB, and optionally a public text-to-SQL benchmark subset if its license allows.

## Evaluation
Details are in docs/eval-plan.md:
- join discovery precision, recall and F1 against gold, with baselines
- view validity and SIT pass rate
- KPI correctness against gold
- text-to-SQL execution accuracy
- SQL red-team block rate
- latency and cost per run

## Demo
- A live URL with a preloaded sample project and no login needed.
- A 2-minute video.
- A README with screenshots and the evaluation table.
- A GIF of the MCP server in use.

## Non-goals
- Not a replacement for BI tools.
- No write-back to source systems.
- No real customer data.
- No SAP connectivity: SAP-style names are used only for realism.

## Risks and mitigations
| Risk | Mitigation |
|---|---|
| Scope creep | Strict milestones, and the MVP gate at M6 before any polish |
| Free-tier LLM rate limits | Small prompts, caching, retries with backoff, fake provider in tests |
| Evaluation honesty | Gold comes from the generator's ground truth, separate dev and test splits, baselines always reported |
| SQL safety | The sqlglot guard, a read-only connection, a red-team test set and the `sql-auditor` subagent |
| Free-tier hosting changes | Verify limits before M11, and keep a Docker image that runs anywhere |
