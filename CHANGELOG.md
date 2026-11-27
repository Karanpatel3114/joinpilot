# Changelog

All notable changes to JoinPilot. Each milestone was built on its own branch and merged as one pull request, one commit per task ([build plan](docs/PLAN.md)).

## [1.1.0] - 2026-11-27

A hardening release from a full audit of the finished project (milestone M13). The deterministic dev-split evaluation is unchanged after the fixes (commit `1a195b0`, [results](eval/results/2026-11-27-1a195b0-dev/metrics.md)): join F1, view validity, check pass rate and attack block rate all stay at 1.000, KPIs at 416 of 416, with 0 harmless queries blocked. Question answering was not rerun (it uses the free model quota); its numbers stay those of 1.0.1.

### Fixed
- **Joins between keys of different types** (an integer column and a text column) are compared as text, the way profiling measured them. Before, the view either failed to build or matched `0005` to `5`.
- **A view that could not be built** now fails a check, so a run can no longer look all green with a view missing.
- **The aging-bucket check** counts open items without a due date. Before, it could never fail.
- Long table and column names no longer overflow the check id column on Postgres.
- A second approval of the same run within an hour is no longer dropped in Redis job mode.
- Derived columns (`due_date`, `aging_bucket`, `X_date`) never shadow uploaded columns of the same name.
- The access guard refuses malformed ids itself, and unknown routes answer in the contract's error shape.
- The console: the sample project no longer flashes upload buttons while loading; run pages stop polling on errors and honour `Retry-After`; cold starts and network errors are explained; true/false answer cells show; saved night mode applies before the first paint.

### Security
- **Uploads past a row limit are refused** before loading (an 8 KB Parquet file could hold 200 million rows), and any work on a project's warehouse is stopped after a time limit.
- **Storage limits:** an hourly budget per client for creating projects and loading tables, at most 20 projects per workspace, and no loads while the disk is nearly full.
- **The workspace id never travels in a URL:** SQL downloads use the `X-Workspace` header (contract 0.15).
- IPv6 clients are rate-limited per /64 network.
- A Content-Security-Policy and Permissions-Policy on the console; CI actions pinned to commit SHAs; a healthcheck on the console image.

## [1.0.1] - 2026-11-27

### Added
- **Question answering measured with Gemini** (dev split, gemini-3.5-flash-lite on the free tier, [results](eval/results/2026-11-27-7c4b16b-dev/metrics.md)): 120 of 160 answers exactly right (75.0%), with free-tier refusals counted as wrong.
- **Model-based join systems measured** over 3 runs: F1 1.000 for both. Only JoinPilot with the model also catches the leading-zero and fan-out cases.
- **An Ask screenshot** in the README showing a real answer, with its chart, rows and guarded SQL.

### Changed
- The default model is pinned to `gemini-3.5-flash-lite`, because Google retired the `gemini-flash-lite-latest` alias.
- The home page drops the caption above the row of tools.

### Fixed
- An Ask panel test that could time out while the tab's code was loading.

## [1.0.0] - 2026-11-26

The first complete release: from raw ERP tables and a plain-English requirement to a tested, human-approved data model, a KPI dashboard and guarded answers to questions, usable from a web console or from Claude through MCP.

### Highlights
- **Final evaluation on the held-out test split** (12 ERP datasets plus TPC-H, commit `1a22e17`, [results](eval/results/2026-11-26-1a22e17-test/metrics.md)): join F1 0.993 with no false positives, against 0.868 for the best baseline; 26 of 26 views valid and 209 of 209 checks passed; 1,248 of 1,248 KPI values right; 71 of 71 SQL attacks blocked.
- **Free public demo** on Render and Vercel, with a read-only sample project built at startup and a private workspace per browser, no login and no payment method anywhere.

### Milestones
- **M0, bootstrap:** uv, FastAPI, React and Vite, CI, the API contract and the project rules.
- **M1, ERP data:** a seeded synthetic ERP generator (SAP-style and friendly names) with planted data-quality issues, gold answers, dev and test splits, and TPC-H.
- **M2, profiling:** column statistics, candidate keys, uniqueness and value-overlap evidence in DuckDB.
- **M3, join candidates:** scored candidates with normalization (leading zeros), fan-out detection and three baselines (name-only, overlap-only, inclusion dependency).
- **M4, agent:** a LangGraph agent that parses the requirement and ranks and explains candidates with the free Gemini tier, behind a provider interface with a fake provider for tests.
- **M5, approval:** a human-approval interrupt with Postgres-backed checkpoints and background jobs (arq and Redis, or threads).
- **M6, views and checks:** guarded SQL views, system-integration checks (row counts, fan-out, orphans, null keys, bucket coverage, reconciliation), automatic repair and export to four SQL dialects.
- **M7, console:** the React console: profile explorer, join graph with evidence, approvals, results.
- **M8, dashboard:** KPI metrics from templates, computed only from views that passed their checks.
- **M9, questions:** plain-English questions answered with guarded, read-only SQL on a sealed connection, plus a 71-attack red-team set.
- **M10, MCP:** an MCP server so Claude Desktop and Claude Code can run the whole workflow.
- **M11, ship it:** Docker images, CI that builds them and runs an evaluation smoke test, rate and size limits, a redesigned console, and free Render and Vercel deployment.
- **M12, polish:** private workspaces per browser, demo mode, the final test-split evaluation, architecture diagrams and limitations.

### Known limitations
See the [Limitations](README.md#limitations) section of the README: synthetic data, single-column joins only, KPI templates for one schema, question answering not yet measured, and workspaces that are not accounts.
