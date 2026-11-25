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

## D-016: One process owns the warehouses; a lock per project inside it
- **Context:** concurrent uploads to one project lost table records, and DuckDB allows only one process to open a database file for writing.
- **Decision:** a single API process owns every project's DuckDB file. Inside it, each project has a re-entrant lock held for every read-change-write of the project's state (record, warehouse tables, cached profile), and JSON files are written atomically through unique temporary files. Background jobs (M5) must run in, or hand their warehouse work to, that same process.
- **Alternatives:** file locks across processes (more moving parts); one DuckDB writer service (an extra service for a portfolio-scale app).
- **Consequences:** no lost writes within a process; uvicorn runs with one worker, which is plenty for this workload.

## D-017: Transparent weighted score with hard rules, not a trained model
- **Context:** candidates need a ranking and an accept/reject decision that a reviewer can audit and an interviewer can follow.
- **Decision:** score = 0.35 × inclusion + 0.35 × name similarity + 0.15 × coverage + 0.15 × key strength, damped by half for N:M pairs. A candidate is proposed only if its target is unique, it scores at least 0.7, it beats the reverse direction, it is the best target for its source column, and (for 1:1 pairs) the names match. Every rejection records its reason. Fan-out risk is flagged when the source table's two-column key pairs the join column with a small column that every key fills (such as a language), and a filter value is suggested. Weights were set on the dev split only; the TPC-H test split was not run.
- **Alternatives:** a learned classifier (needs labelled schemas we do not have, and is harder to explain); LLM-only proposals (measured as an ablation in M4).
- **Consequences:** fully explainable decisions. Fuzzy name matches are capped at half credit so code columns such as WAERK and WAERS do not look like keys.

## D-018: Baselines that each use one kind of evidence, plus the textbook rule
- **Context:** an F1 score means little on its own; the evaluation plan asks for simple baselines next to every number.
- **Decision:** three baselines. Name-only (names and type family, direction guessed from column position, as a person reading the DDL would); overlap-only (inclusion of at least 95%, nothing else); and the textbook inclusion-dependency rule (inclusion of at least 90% into a unique column from a non-unique one). Metrics are micro-averaged and every gold edge stays in every denominator: a missed join counts against recall, normalization recall, fan-out recall and filter accuracy. Fan-out precision catches false fan-out flags.
- **Consequences (dev, commit `ccdeaf3`):** names alone find every join but propose almost three times too many (precision 0.37, F1 0.54) and never normalize; overlap alone accepts decoys such as currency codes (precision 0.27). The inclusion-dependency rule also reaches F1 1.0 on dev, so on this split uniqueness does most of the work; JoinPilot's dev advantage is fan-out detection with the right filter. The earlier run at `85cc117` used a normalization metric that left missed joins out of its denominator; it is kept for history but superseded.

## D-019: A Flash-Lite model by default, and an app that works without any model
- **Context:** in late 2026 the Gemini free tier allows only about 20 requests a day on the main Flash model, but hundreds on Flash-Lite (figures vary by project; check AI Studio). The public demo and the evaluation must stay free, and a missing key or an exhausted quota must not break the app.
- **Decision:** the default model is the `gemini-flash-lite-latest` alias, set in config. Structured output uses Gemini's JSON-schema mode (Gemma models get the schema in the prompt). Without a key, `UnavailableProvider` raises `LLM_UNAVAILABLE` on every call, and each agent step falls back to its deterministic behavior. Cost estimates use configurable list prices and default to $0, since free-tier calls are not billed.
- **Alternatives:** a Pro model (paid only); a local Ollama model (too heavy for the free hosting tier and an 8 GB laptop).
- **Consequences:** the whole product runs, and is tested, with no key; quality improves when a key is present.
- **Status at the end of M4:** no key was configured yet, so the LLM-only ablation and the full agent have not been run against the model. `uv run python -m eval.run_all --split dev --llm` records those numbers once a key is set; until then the README reports only deterministic systems.

## D-020: When the model may overrule the scorer
- **Context:** the model ranks candidates in the context of the requirement, so it may usefully drop a join the requirement does not need, or recommend a near-miss the scorer rejected only for a low score. It must never weaken a hard rule.
- **Decision:** the model's include decision counts only for edges whose explanation passes the evidence check. It may drop any accepted join. It may rescue a rejected join only when the scorer's sole objection was a low score, the cardinality is N:1 or 1:1 and the score is at least `AGENT__RESCUE_MIN_SCORE`; never past the uniqueness, 1:1 or best-target rules. Edges whose explanations fail after one corrective retry, or that the model omits, get the scorer's decision and a template explanation; if the retry call itself fails, grounded first answers are kept. Every rescue, failure and omission is reported as a warning and counted for evaluation.
- **Consequences:** model mistakes can lower quality only in visible, counted ways, never by smuggling in an unsupported join.

## D-021: Approval as a LangGraph interrupt with a database checkpointer
- **Context:** no view may be built until a person approves the joins, and the person may answer minutes or days later, after the process that ranked the joins has gone.
- **Decision:** the graph's `await_approval` step calls LangGraph's `interrupt`, and every step's state is saved by a checkpointer in the application database (LangGraph's PostgresSaver; a SQLite file locally), keyed by run id. Resuming with `Command(resume=decisions)` in any process continues from the saved state. Decisions on unknown joins are ignored with a warning; if nothing is approved the run completes without views. Alembic ignores the checkpointer's own tables.
- **Alternatives:** storing a "waiting" flag and re-running the pipeline on approval (repeats model calls and can rank differently); a hand-written state machine (D-003).
- **Consequences:** approval is a real pause with durable state; a test resumes a run from its checkpoint in a new graph instance, on SQLite and on Postgres.

## D-022: The arq worker runs inside the API process by default
- **Context:** agent runs must not block HTTP requests and should survive restarts, but one process must own each project's DuckDB file (D-016), and the free hosting tier gives one small container.
- **Decision:** jobs go through a `JobQueue`: inline (tests), a thread pool (local, no Redis), or Redis with arq. In arq mode the API's lifespan starts an arq worker in the same process, so DuckDB ownership is unchanged while jobs are durable, de-duplicated by a job id per run step, limited in concurrency and timed out. A standalone `arq joinpilot.jobs.worker.WorkerSettings` exists for setups where the API never writes warehouses at the same time.
- **Alternatives:** a separate worker container (DuckDB write conflicts, and a second paid-tier service); FastAPI background tasks (lost on restart).
- **Consequences:** one container to deploy; an integration test drives a run through Redis and the in-process worker from start to approval to completion.

## D-023: Local hashed embeddings for the glossary, searched with pgvector
- **Context:** questions and requirements use business words ("customer name", "open receivable amount") while ERP columns have cryptic names (NAME1, DMBTR). Matching them needs a similarity search, and the free model quota is better spent on reasoning.
- **Decision:** each column gets a plain-words description (public SAP-style field meanings for known names, the split column name otherwise) and a 256-dimension embedding built locally from hashed word and character-trigram features. Postgres stores it in a pgvector column and orders by cosine distance; SQLite stores a JSON list and the same search runs in Python. The glossary is rebuilt after any table change. An exact scan is used because a project has hundreds of columns, not millions; an HNSW index is the upgrade path.
- **Alternatives:** Gemini embeddings (semantic, but uses quota and needs a key); full-text search (no similarity scores, weaker on partial words).
- **Consequences:** free, deterministic, offline search that a test shows gives the same top matches and scores on pgvector and in Python; synonyms with no shared letters ("client" and "customer") are not matched.

## D-024: Runs are a compare-and-set state machine; jobs are idempotent
- **Context:** review reproduced a completed run flipping back to "awaiting approval" when a start job was redelivered, a status set before the pause was saved, two approvals racing, and a failed enqueue leaving a run stuck forever.
- **Decision:** every status change is a single `UPDATE ... WHERE status IN (...)`, so only one caller wins and completed or failed runs never change. Jobs never trust the status alone: they read the saved checkpoint and do only what is left (start, resume once decisions exist, continue after a restart, or nothing). The graph is streamed with synchronous durability, and "awaiting approval" is set only after the pause is saved. A failed enqueue fails a new run or restores the pause, and returns 503. Thread mode re-queues active runs on startup; an arq time-out marks the run failed. Errors shown to users are safe messages; details stay in the log.
- **Consequences:** duplicate or redelivered jobs are harmless, which also makes arq's redelivery on shutdown a feature rather than a bug; tests cover each reproduced case.

## D-025: An allowlist SQL guard built on sqlglot's parser and qualifier
- **Context:** model output and user questions become SQL that runs on the project's warehouse. DuckDB can read files and URLs (`read_csv`, `FROM 'file.csv'`), attach databases and change settings, so a blocklist of keywords is not enough.
- **Decision:** parse with sqlglot (DuckDB dialect); allow exactly one statement; allow only a query (or, for model generation, `CREATE OR REPLACE VIEW` in the `model` schema); refuse any DDL, DML or command node anywhere in the tree; allow only functions on an explicit allowlist (so every table function is refused); and resolve every table and column against the project's catalog with sqlglot's `qualify`, which also expands `*`. The guard returns the normalized SQL that is then executed.
- **Alternatives:** keyword or regex blocklists (easy to bypass with comments, case or nesting); DuckDB settings alone such as disabling external access (not available for every attack, and a single layer).
- **Consequences:** safe by construction for unknown functions; some legitimate functions may need adding to the allowlist, which is a one-line, reviewed change.
