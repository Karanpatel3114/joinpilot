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
- **Decision:** the default model is a free-tier Flash-Lite model, set in config: first the `gemini-flash-lite-latest` alias, pinned to `gemini-3.5-flash-lite` in November 2026 after Google retired the alias (a pinned name fails loudly instead of changing silently). Structured output uses Gemini's JSON-schema mode (Gemma models get the schema in the prompt). Without a key, `UnavailableProvider` raises `LLM_UNAVAILABLE` on every call, and each agent step falls back to its deterministic behavior. Cost estimates use configurable list prices and default to $0, since free-tier calls are not billed.
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

## D-026: Deterministic repair of structural check failures
- **Context:** a person can approve a join that multiplies rows (for example order items to product texts in two languages). Checks catch it; the spec asks the agent to repair failures in up to two attempts.
- **Decision:** only structural failures are repaired: row counts, duplicate fact keys and totals that do not reconcile. For each join whose target is not unique, the repair either filters the target to one row per key (when a small code column such as a language fills every key, choosing the configured preferred value) or removes the join and the branch that hung on it, then re-renders the view through the guard and re-runs the checks. Orphan and null keys describe the data, so they are reported, not "fixed". Each repair is explained in the run's warnings and the view is marked `repaired`.
- **Alternatives:** asking the model to rewrite the SQL (harder to guarantee, needs a key); failing the run (leaves the person with nothing usable).
- **Consequences:** repairs are predictable and testable; a test shows a bad approval repaired with `SPRAS = 'E'` and every structural check passing afterwards.

## D-027: Export to other warehouses by transpiling with sqlglot
- **Context:** views are built and tested in DuckDB, but teams run models in Postgres, Snowflake or BigQuery.
- **Decision:** transpile each view with sqlglot after rewriting DuckDB-only functions into sqlglot's typed equivalents (`try_strptime` becomes a safe date parse, which Snowflake renders as `TRY_TO_TIMESTAMP` and BigQuery as `SAFE_CAST ... FORMAT`). Anything a dialect cannot express is reported next to the SQL rather than dropped; Postgres gets a note that its date parsing is not safe.
- **Alternatives:** hand-written templates per dialect (more code and drift); dbt project export (a planned stretch goal).
- **Consequences:** one source of truth with checked translations; tests parse every exported view back in its dialect and re-run the DuckDB script against the raw tables.

## D-028: Show DuckDB views pretty-printed, not as the stored text
- **Context:** the views are stored and run as one compact line each, which is hard to read in the console and in a downloaded script.
- **Decision:** the export layer re-renders DuckDB SQL with sqlglot's pretty printer, the same path the other dialects already take. The stored SQL that ran is unchanged; only what is shown and downloaded is formatted.
- **Alternatives:** generate pretty SQL in the first place (touches the guarded view builder for a display concern); format in the browser (a second SQL formatter to keep in step).
- **Consequences:** a test builds every fixture view from both texts and requires identical rows, so the formatting cannot silently change what a view returns.

## D-029: Dashboard metrics from deterministic templates
- **Context:** M8 needs KPI definitions that are correct enough to be measured against gold, from views whose column names follow either SAP-style or readable naming.
- **Decision:** metrics are templates (aging buckets, top customers by open amount, revenue by product group, orders per month, top customers by revenue) that apply only when the model has the columns they need. Columns are found by meaning, from field hints or readable names, and through the approved joins (a customer table is one reached on a customer key). Header-level money is reduced to one row per header before summing, so items cannot double it. The requirement decides which metrics are marked as asked for and shown first, and a year in the requirement becomes a filter.
- **Alternatives:** let the LLM write metric SQL (untestable without a key, and unsafe to trust for numbers leaders read); a full semantic layer such as dbt metrics (far more than five KPIs need).
- **Consequences:** KPI numbers are reproducible and testable offline, and every metric's SQL goes through the guard. New KPI kinds need a new template; free-form questions are M9's job.

## D-030: One run per project builds its model at a time
- **Context:** views have fixed names (`v_<fact>`) in one model schema per project, so two runs building at once could check, or compute KPIs on, each other's views.
- **Decision:** approving a run gives 409 while another run of the same project is generating, checking or repairing, checked under a per-project lock in the service. Starting runs and waiting for approval stay unrestricted, so an abandoned run never blocks the project. The dashboard belongs to the most recently completed run, because its model is the one in the warehouse.
- **Alternatives:** a schema per run (more storage and a moving target for questions and MCP); a queue that serialises builds (more moving parts for a rare case).
- **Consequences:** numbers are always stored under the run whose views produced them. The lock is per process, which fits the single API process with an in-process worker; several API processes would need a database lock instead.

## D-031: Questions read the tested views first and raw tables for single-table facts
- **Context:** each model view keeps every row of one fact table, so a question about one table's own records ("how many customers are in Germany?") cannot be answered from the views without undercounting (customers with no open items disappear).
- **Decision:** the semantic model lists the newest run's views first, as the preferred source, then the raw tables, marked for questions about one table's own records only. The guard's catalog is the model schema plus the raw tables; both run read-only under the same row limit and timeout. One function, `qa.answer.answer_question`, is shared by the API, the MCP server and the evaluation.
- **Alternatives:** views only (wrong answers for master-data questions); generating a view per master table (more objects to keep in step, for little gain).
- **Consequences:** the model could re-join raw tables itself and skip an approved normalization; the prompt forbids it and the evaluation's normalization-tagged questions measure it.

## D-032: A stricter guard mode for questions, and a guard that fails closed
- **Context:** the guard stopped every read and write, but a model-written query could still build gigabyte strings from tiny input (padding to a computed length, nested `replace`, aggregating text over a cross join) and exhaust the API's memory within the row limit and timeout. Some inputs also crashed the parser and returned 500.
- **Decision:** in every mode, padding and repeating need an integer literal length of at most 10,000. Questions use a `question` mode that also refuses the value-growing functions (`lpad`, `rpad`, `replace`, `regexp_replace`, `string_agg`, `group_concat`, `array_agg`, `concat_ws`); generated views and metrics never need them from the model. Any unexpected error while checking is a refusal.
- **Alternatives:** limit only at execution (a 1 GB string is built before any row is returned); bound growth per function (complex and easy to get wrong).
- **Consequences:** questions cannot normalize keys themselves; the views already do. The red-team eval reports the harmless queries the question mode refuses, alongside the select-mode rate.

## D-033: The MCP server lives in the package and runs jobs inline
- **Context:** M10 lets Claude Desktop, Claude Code and other MCP clients drive JoinPilot. The repo map reserved `mcp/`, but a top-level `mcp` Python package would shadow the official SDK, which is also imported as `mcp`.
- **Decision:** the server is `joinpilot.mcp_server` (run with `python -m joinpilot.mcp_server` or `joinpilot-mcp`) on the official SDK's `MCPServer` over stdio; `mcp/` holds only the setup guide and client config. Tools call the same services as the API and run jobs inline, so each tool returns when its step is done. Approval stays a separate tool whose description tells the assistant to ask the user first.
- **Alternatives:** call the HTTP API from the MCP server (a second process to run and keep in step); a background queue (the assistant would have to poll).
- **Consequences:** long steps block the tool call for seconds, which MCP clients handle. The MCP server and the API can share a data folder, but DuckDB allows one writer per warehouse file at a time, so the same project should not be modified from both at once.

## D-034: One backend image, a static web image, and the demo fits in 512 MB
- **Context:** M11 ships JoinPilot on free hosting, where the API gets about 512 MB of memory and the console can be static files.
- **Decision:** one backend image (uv-built, non-root, Python 3.12 slim) runs the API with its in-process worker (D-022); the same image runs a standalone arq worker or the MCP server by changing the command. The console is a static Vite build served by unprivileged nginx with an SPA fallback and security headers. Base images and uv are pinned to releases at least two weeks old. Compose gains an opt-in `app` profile that runs the whole stack.
- **Alternatives:** separate worker and API images (the same code twice); serving the console from the API (couples deploys and caching).
- **Consequences:** a full run (sample load, profiling, approval, views, checks, dashboard) uses about 190 MB with `DUCKDB_MEMORY_LIMIT=256MB`, and the Playwright happy path passes against the containers. The backend image is about 870 MB because of pyarrow, DuckDB and numpy.

## D-035: In-memory rate limits per client, with a global budget for model calls
- **Context:** the public demo has no login and runs on a free model quota and a 512 MB host; one visitor or script must not exhaust either.
- **Decision:** a small ASGI middleware counts requests per client IP in fixed windows: a general per-minute budget, tighter per-minute and per-day budgets for starting runs and asking questions (the model-backed calls), and a global daily budget for those across everyone. JSON bodies are capped; uploads keep their own limit. Refusals use the contract's error body (429 `RATE_LIMITED` with `Retry-After`, 413) and pass through CORS so the console can show them.
- **Alternatives:** Redis-backed limits (needed only with several API processes); a gateway or CDN rule (not available on the free hosts).
- **Consequences:** counters reset when the process restarts and are per process, which fits the single API process. Behind a proxy the client IP is the `X-Forwarded-For` entry the trusted proxies appended, counted from the right (`LIMITS__FORWARDED_HOPS`, 1 on Render); entries further left are written by the client and ignored, and uvicorn no longer trusts forwarded headers itself. A request is checked against every budget before any is counted, so a refused request spends nothing, and the counter table is capped at 50,000 windows (finished ones pruned, then the oldest dropped). Bodies without a length are read up to the cap before the endpoint runs, so they get the same 413.

## D-036: Host the API on Render's free plan and the console on Vercel, with no paid services
- **Context:** M11 needs a public demo that can never bill the owner. In November 2026, Render's free web service gives 512 MB and 0.1 CPU and sleeps after 15 idle minutes, with a disk that is wiped on restart; Vercel Hobby serves static sites for personal, non-commercial use; Neon and Upstash have free tiers, but Upstash switches to pay-as-you-go once a card is added.
- **Decision:** a Render Blueprint (`render.yaml`) runs the backend image as one free web service with SQLite and in-process jobs (`JOBS_MODE=thread`); Vercel builds the console from `web/` (`web/vercel.json`, SPA fallback and the same security headers as nginx) with `VITE_API_URL` pointing at Render. No Postgres or Redis in production. The backend Dockerfile drops BuildKit cache mounts so any Docker builder can build it.
- **Alternatives:** adding Neon (Postgres) and Upstash (Redis) for durable state (two more accounts, and the demo is meant to reset); Hugging Face Spaces (free CPU restricted for new accounts in 2026); serving the console from the API (one service, but a cold API would also hide the page).
- **Consequences:** two sign-ups, no card anywhere. The first request after a quiet spell waits about a minute while Render wakes the API. Data lasts until the next restart, so the demo preloads its sample project at startup (M12.2). Postgres, Redis and arq remain supported and tested in Docker Compose and CI.

## D-037: Private workspaces per browser instead of a login
- **Context:** the public demo lets anyone upload tables and start runs, so visitors must not see each other's projects. The plan named Supabase sign-in, but a login screen stops most recruiters from trying the demo, and it adds an outside account.
- **Decision:** the console makes a random 128-bit workspace id once per browser (local storage) and sends it as `X-Workspace` on every request (`?workspace=` on download links). Projects store their workspace; one API dependency checks every route with a `project_id` or `run_id` and answers 404 for another workspace's project, so existence is not revealed. Calls without an id (MCP server, scripts, tests) use the `local` workspace. A shared `demo` workspace holds the preloaded sample project, readable by all and changeable by none (409).
- **Alternatives:** Supabase or GitHub sign-in (real accounts, but friction and another service); one shared space (simplest, but visitors see each other's uploads); signed cookies (needs a secret and cross-site cookie settings between Vercel and Render).
- **Consequences:** no account, no cost and no login screen. The id is a bearer secret, like an unguessable link: anyone who has it can use that workspace, and clearing browser storage loses access to old projects (they vanish anyway when the free host restarts). It is not authentication, and the README says so.
