---
paths:
  - "backend/joinpilot/sqlgen/**"
  - "backend/joinpilot/checks/**"
  - "backend/joinpilot/qa/**"
  - "backend/joinpilot/kpi/**"
  - "mcp/**"
---
# SQL safety rules

All SQL produced by an LLM, or built from user input, is untrusted. Everything goes through `joinpilot.sqlgen.guard` before it runs.

- Parse every statement with sqlglot (DuckDB dialect). If parsing fails, reject it.
- Allow exactly one statement per call.
- Allowed statements: `SELECT` (including `WITH`) for questions and checks; `CREATE OR REPLACE VIEW` inside the project's sandbox schema for model generation. Everything else is rejected, including DROP, DELETE, UPDATE, INSERT, ALTER, ATTACH, DETACH, COPY, EXPORT, PRAGMA, INSTALL, LOAD, SET and CALL.
- Reject table functions and file or network access (for example `read_csv`, `read_parquet`, `read_json`, `glob`, `httpfs` and URLs or paths in string literals used as tables).
- Tables and columns must exist in the project's catalog (an allowlist built from profiling). Unknown identifiers are rejected.
- Questions run on a read-only DuckDB connection with a row limit (default 1,000, from config) and a statement timeout (from config).
- Never build SQL by string concatenation with user input. Put user values in as parameters, and quote identifiers with sqlglot.
- Log every executed statement with its run ID, duration and row count, but never log row data.
- Every new guard rule gets at least one case in `eval/redteam/sql_attacks.jsonl` and a test proving it is blocked. Run the `sql-auditor` subagent after changes here.
