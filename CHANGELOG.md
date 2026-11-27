# Changelog

All notable changes to JoinPilot. Each milestone was built on its own branch and merged as one pull request, one commit per task ([build plan](docs/PLAN.md)).

## [1.0.0] - 2026-11-26

The first complete release: from raw ERP tables and a plain-English requirement to a tested, human-approved data model, a KPI dashboard and guarded answers to questions, usable from a web console or from Claude through MCP.

### Highlights
- **Final evaluation on the held-out test split** (12 ERP datasets plus TPC-H): join F1 0.993 with no false positives, against 0.868 for the best baseline; 26 of 26 views valid and 209 of 209 checks passed; 1,248 of 1,248 KPI values right; 71 of 71 SQL attacks blocked.
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
