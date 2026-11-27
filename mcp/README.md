# JoinPilot MCP server

JoinPilot's whole workflow is available as [Model Context Protocol](https://modelcontextprotocol.io) tools, so an assistant such as Claude Code or Claude Desktop can profile tables, propose joins, build and check the model, read the KPI dashboard and answer questions, using the same code and safety rules as the web console.

The server is part of the Python package (`joinpilot.mcp_server`, on the official MCP Python SDK) and talks over stdio. It reads the same `.env` and data folder as the API.

## Set up

Prerequisites: the repository cloned and `uv sync` run once. A `GEMINI_API_KEY` in `.env` is optional; without it, ranking falls back to the deterministic scorer and questions explain that the language model is off.

**Claude Code** (from anywhere):

```bash
claude mcp add joinpilot -- uv run --directory /absolute/path/to/joinpilot joinpilot-mcp
```

**Claude Desktop**: open Settings → Developer → Edit Config and add the `joinpilot` entry from [`claude_desktop_config.example.json`](claude_desktop_config.example.json), with your path. Claude Desktop often does not see your shell's PATH, so use the absolute path to `uv` (from `which uv`, for example `/Users/you/.local/bin/uv`) as the command. Restart Claude Desktop.

**Any other client**: run `uv run joinpilot-mcp` (or `uv run python -m joinpilot.mcp_server`) from the repository folder as a stdio server.

## Tools

| Tool | What it does |
|---|---|
| `list_projects` | Projects and their tables |
| `create_project` | A new, empty project |
| `load_sample` | Loads the synthetic SAP-style ERP sample (six tables with planted data-quality issues) |
| `profile_tables` | Row counts, candidate keys, and per column type, null rate, distinct values and uniqueness |
| `propose_joins` | Starts a run for a requirement: profiles, ranks join candidates with evidence, and stops for approval |
| `approve_joins` | Approves chosen joins by edge id (omitted: the recommended ones; unknown ids are refused), then builds the views, runs the checks with repair and builds the dashboard |
| `get_run` | A run's status, proposals, views and check summary |
| `get_check_results` | Every check: row counts, fan-out, orphan and null keys, aging coverage, reconciliation |
| `get_dashboard` | The KPI metrics of the newest completed run, with their SQL |
| `ask_question` | Answers a question with guarded, read-only SQL and shows the SQL and evidence |
| `export_sql` | The model as one SQL script for DuckDB, Postgres, Snowflake or BigQuery |

## Example

> **You:** Load the ERP sample into a new project and propose joins for "open receivables by customer and aging bucket".
>
> **Claude** calls `create_project`, `load_sample` and `propose_joins`, then summarises: 25 candidates, 5 recommended. For example, `BSID.KUNNR → KNA1.KUNNR` needs customer numbers padded with zeros to 10 characters (97% of values then match, and KNA1.KUNNR is unique).
>
> **You:** Approve the recommended joins.
>
> **Claude** calls `approve_joins`: the run completes with views `v_bsid` and `v_vbap`, and 15 of 15 checks pass. It then calls `get_dashboard` and reports open receivables per aging bucket.

The tests in [`backend/tests/mcp_server/test_tools.py`](../backend/tests/mcp_server/test_tools.py) run this flow through a real MCP client (the numbers above are from the offline sample run without a model key).

## Safety

- Nothing is built until `approve_joins` is called, and its description tells the assistant to ask the user first. Read-only tools carry the MCP `readOnlyHint`, so clients can allow them freely and still ask before `propose_joins` and `approve_joins`.
- Inputs have the same limits as the API (project names 1 to 100 characters, requirements 3 to 2,000, questions up to `QA__MAX_QUESTION_CHARS`).
- Questions follow the same rules as the API. The SQL must pass the guard (the newest model's views and the raw tables only, nothing that can grow values). It runs on a read-only connection without file or network access, with a row limit, an answer-size limit and a timeout.
- Domain errors come back as tool errors with a plain message, for example `NOT_FOUND: Project not found.`
- DuckDB allows one writer per warehouse file at a time, so don't change the same project from the web console and an assistant at the same moment.
- The MCP server runs on your own machine and works in the `local` workspace (D-037). It skips the browser workspace checks and can change the demo project, so don't expose it beyond a trusted, local process.
