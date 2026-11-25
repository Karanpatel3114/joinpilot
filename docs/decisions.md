# Decision log

One entry per design choice that had real alternatives. Newest at the bottom. Format: context, decision, alternatives, consequences.

## D-001: DuckDB for profiling and the sandbox warehouse
- **Context:** we need fast column statistics and a safe place to run generated SQL on uploaded files, on a laptop and on free hosting.
- **Decision:** one DuckDB file per project.
- **Alternatives:** Postgres for everything (slower analytics, riskier to run generated SQL in the app database); pandas (no SQL, memory-heavy).
- **Consequences:** fast and simple. Analytics data stays separate from app state. Dialect export through sqlglot is needed for other warehouses.

## D-002: Deterministic candidates, LLM ranking
- **Context:** LLMs can invent plausible but wrong joins.
- **Decision:** profiling and candidate generation are pure code. The LLM only ranks and explains candidates, citing evidence IDs, and a validator rejects unsupported claims.
- **Alternatives:** LLM-only join proposals.
- **Consequences:** fewer hallucinated joins, and claims that can be audited. The LLM-only ablation in evaluation measures the difference.

## D-003: LangGraph for the agent
- **Context:** the workflow needs multiple steps, a pause for human approval, retries and resumable state.
- **Decision:** LangGraph with interrupts and the Postgres checkpointer.
- **Alternatives:** a hand-written state machine; LangChain agents without a graph.
- **Consequences:** explicit, testable steps, and runs that resume. It adds a dependency the team must learn.

## D-004: Postgres with pgvector for app state and the glossary
- **Context:** projects, runs, approvals and checkpoints need durable storage, and matching business terms to columns needs vector search.
- **Decision:** one Postgres database with the pgvector extension.
- **Alternatives:** SQLite plus FAISS (no hosted option with good concurrency); a dedicated vector database (an extra service).
- **Consequences:** one database to run, and free hosted options exist.

## D-005: Gemini behind a provider interface
- **Context:** a free tier is needed, along with offline tests and the freedom to switch models.
- **Decision:** a `LLMProvider` interface with Gemini (default), a fake provider for tests, and optional Ollama.
- **Consequences:** tests never call the network. Swapping models is a config change.

## D-006: uv for Python environments
- **Decision:** uv with a committed `uv.lock`.
- **Alternatives:** pip with requirements.txt; Poetry.
- **Consequences:** fast, reproducible installs locally and in CI.

## D-007: Synthetic SAP-style data
- **Context:** realistic ERP data is needed without any real company data.
- **Decision:** a seeded generator with SAP-style and friendly naming, planted issues, and gold written by the generator.
- **Consequences:** a known ground truth for evaluation. Generator code is reviewed as carefully as app code.

## D-008: arq with Redis for background jobs
- **Context:** agent runs can take longer than one HTTP request.
- **Decision:** arq workers with Redis, and status polling from the console.
- **Alternatives:** FastAPI background tasks (lost on restart); Celery (heavier).
- **Consequences:** an extra service in Docker and in production (Upstash free tier).

## D-009: One commit per task, one pull request per milestone
- **Decision:** small conventional commits pushed as they happen; each milestone merged with a merge commit after CI and review.
- **Consequences:** a readable history that shows how the project was built.
