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

## D-010: Gold computed in Python, cross-checked with SQL
- **Context:** evaluation is only as honest as its answers. Gold computed with the same SQL that JoinPilot generates would share its mistakes.
- **Decision:** the generator computes gold in plain Python from the rows it created; a test recomputes the KPIs and several answers with DuckDB SQL over the written Parquet files and requires an exact match.
- **Alternatives:** gold from SQL only (shares blind spots); hand-written answers (do not scale, drift).
- **Consequences:** two independent implementations must agree, and money is generated as integer cents so sums compare exactly.

## D-011: One random stream per table and per planted issue
- **Context:** the data must be byte-identical for a given seed, and adding a feature must not silently change every other table.
- **Decision:** each table and issue draws from `numpy.random.default_rng([seed, crc32(name)])`.
- **Alternatives:** one shared generator (any change reshuffles everything downstream).
- **Consequences:** stable datasets across generator changes; a determinism test hashes the output files.

## D-012: Aging buckets measured in days past the due date
- **Context:** the spec named buckets "0–30" and "not due", which overlap at day 0.
- **Decision:** days overdue = reference date − (baseline date + payment days); `not_due` is ≤ 0 (due today or later), then `1-30`, `31-60`, `61-90` and `90+`.
- **Consequences:** buckets are disjoint and cover every item; docs/data-model.md records the definition.

## D-013: Distribution shapes stay in code; issue rates live in config
- **Context:** the config rule says every tunable number lives in config, but the generator also has shape constants (payment terms, discount levels, the Zipf exponent, price and amount distributions, the average age of open items).
- **Decision:** the planted-issue rates, sizes, dates and currency mix are in `SynthSettings`, because experiments vary them. Shape constants stay as named module constants, because changing any of them changes every dataset and must go together with regenerated gold and a new pinned fingerprint.
- **Alternatives:** everything in config (makes it easy to change the data without noticing that gold is now stale).
- **Consequences:** the data's realism lives in a few readable constants; the fingerprint test guards them.

## D-014: Type CSV columns ourselves, keeping zero-padded ids as text
- **Context:** DuckDB's CSV sniffer, like most tools, reads `0000100023` as the number 100023, which destroys exactly the leading-zero evidence that join discovery depends on.
- **Decision:** read CSV files as all-text, then cast each column: integers only when no value has a leading zero, decimals, ISO dates, and text otherwise. Parquet keeps its own types.
- **Alternatives:** trust the sniffer (silently corrupts ERP keys); keep everything as text (loses numeric statistics).
- **Consequences:** uploads keep ERP keys intact; the rule is explicit and tested.

## D-015: All pairwise overlaps from one self-join over distinct values
- **Context:** inclusion scores are needed for every ordered pair of key-like columns in different tables, which is hundreds of pairs (about 650 for the ERP sample, more for TPC-H).
- **Decision:** stack the distinct values of every integer or short text column into one temporary "long" table `(column, table, value)`, sample each source column deterministically (ordered by `hash(value)`) to a configured size, and count matches for all pairs with a single hash join that skips same-table pairs.
- **Alternatives:** one `IN` query per pair (hundreds of scans); MinHash sketches (approximate, harder to explain as evidence).
- **Consequences:** exact counts for unsampled columns, about 0.03 s on the ERP sample and 0.12 s on TPC-H SF 0.1. Decimal, float, date and long text columns are never compared, which also rejects several decoys by construction.
