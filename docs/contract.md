# JoinPilot API contract

Version: 0.7. Change it only with the `contract-sync` skill, and bump the version.

Changes in 0.7 (additive): `GET /runs/{run_id}/views` takes `?dialect=`; `GET /runs/{run_id}/export` downloads the model as one SQL script.

Changes in 0.6 (additive): the views and checks endpoints are implemented; `View` gains `fact_table`, `joins`, `derived_columns` and `message`.

Changes in 0.5 (additive): `GET /projects/{project_id}/glossary` searches columns by business words.

Changes in 0.4 (additive): the run endpoints are implemented; `Run` gains `project_id`, `warnings`, `created_at` and `updated_at`; proposals gain `filter`, `explanation_source`, `relevance`, `recommended`, `rescued`, `rejection_reason` and `decision_reason`; `GET /projects/{project_id}/runs` lists runs. The views and checks endpoints arrive in M6.

Changes in 0.3 (additive): profile columns gain `non_null_count` (exact count, used for uniqueness evidence); table names that differ only by case refer to the same table.

Changes in 0.2 (additive, no breaking changes): `POST /projects` and `POST /projects/{project_id}/tables` return 201; the profile gains a top-level `keys` list (uniqueness evidence, `uk_` ids), extra column statistics, and extra overlap fields; error codes are listed.

Example responses live in `shared/fixtures/` and are validated against the backend schemas by `backend/tests/api/test_contract.py`.

All responses are JSON. Errors use `{"error": {"code": "STRING_CODE", "message": "plain-language message", "details": {}}}`. IDs are UUID strings. Times are ISO 8601 in UTC.

Error codes: `NOT_FOUND` (404), `INVALID_INPUT` (422, also for malformed requests, with `details.fields`), `CONFLICT` (409), `PAYLOAD_TOO_LARGE` (413), `INTERNAL_ERROR` (500).

## Health
`GET /health` returns `{"status": "ok", "version": "0.1.0"}`

## Projects and tables
`POST /projects` with `{"name": "Demo ERP"}` (1–100 characters, trimmed) returns 201 and `Project {id, name, created_at, table_count}`

`GET /projects` returns `[Project]`, newest first.

`POST /projects/{project_id}/tables` takes either a multipart upload (field `files`, one or more CSV or Parquet files; maximum size `MAX_UPLOAD_MB` per file) or JSON `{"sample": "erp_s1_sap"}` (sample ids are `erp_<size><seed>_<naming>` with size `s` or `m` and naming `sap` or `friendly`). Returns 201 and `[TableSummary {table_id, name, row_count, column_count}]`. Uploading a file whose table name already exists (ignoring case) replaces that table and keeps its `table_id`. File types are checked for the whole batch before anything loads; files then load in order, so if a later file fails to parse, earlier files in the same request stay loaded and the error names the failed file. CSV columns are typed so zero-padded ids stay text.

`GET /projects/{project_id}/profile` returns (computed on first request after any table change, then cached):
```json
{
  "tables": [{"table_id": "...", "name": "VBAK", "row_count": 10000,
    "columns": [{"name": "KUNNR", "type": "VARCHAR", "null_pct": 0.0, "non_null_count": 10000,
      "distinct_count": 819, "sample_values": ["0000100094"], "is_key_candidate": false,
      "min_value": "0000100094", "max_value": "0000999162", "max_length": 10,
      "fixed_length": 10, "digits_only": true}],
    "candidate_keys": [["VBELN"]]}],
  "keys": [{"evidence_id": "uk_010", "table": "KNA1", "columns": ["KUNNR"],
    "distinct_count": 1000, "non_null_count": 1000, "uniqueness": 1.0}],
  "overlaps": [{"evidence_id": "ov_005", "from": "BSID.KUNNR", "to": "KNA1.KUNNR",
    "inclusion_ratio": 0.969984, "raw_inclusion_ratio": 0.0, "normalization": "lpad_zeros:10",
    "checked_values": 633, "matched_values": 614, "sampled": false}]
}
```
- `keys` holds the uniqueness (distinct ÷ non-null rows) of every integer or text column and of every composite candidate key.
- `overlaps` holds, for ordered column pairs in different tables, the share of distinct `from` values found in `to` (only pairs at or above `overlap_min_ratio`). `normalization` is `none`, `lpad_zeros:<width>` (pad the `from` side), `strip_leading_zeros` or `trim_upper` (both sides); `raw_inclusion_ratio` is the ratio before normalization. `sampled` is true when the `from` column had more distinct values than `overlap_sample_size`.
- Evidence ids are assigned in sorted order and are stable for the same data.

`GET /projects/{project_id}/glossary?q=customer%20name&k=5` returns the `k` (1–20, default 5) columns whose business description best matches `q` (1–200 characters):
```json
[{"column": "KNA1.NAME1", "description": "name of customer master (KNA1.NAME1)", "score": 0.6123}]
```
Descriptions use plain words for SAP-style names (KUNNR is "customer number") and the column name otherwise; `score` is the cosine similarity of local text embeddings (pgvector on Postgres). The glossary is rebuilt after any table change.

## Runs (agent)
`POST /projects/{project_id}/runs` with `{"requirement": "Open receivables by customer and aging bucket"}` (3–2000 characters) returns 202 and a `Run`. The run continues in the background: it profiles, parses the requirement, ranks and explains joins, then waits for approval. A project without tables gives 409.

`GET /projects/{project_id}/runs` returns `[Run]`, newest first.

`GET /runs/{run_id}` returns (poll it to follow progress):
```json
{"run_id": "...", "project_id": "...", "status": "awaiting_approval",
 "requirement": "Open receivables by customer and aging bucket",
 "parsed_requirement": {"summary": "...", "entities": ["customer", "receivable"],
   "measures": [{"name": "open amount", "description": "sum of open item amounts"}],
   "dimensions": ["aging bucket"], "filters": [{"field": "year", "operator": "=", "value": "2026"}],
   "relevant_tables": ["BSID", "KNA1"], "source": "llm"},
 "error": null, "warnings": ["Keyword parsing used: GEMINI_API_KEY is not set, so the language model is off."],
 "timings_ms": {"profile": 210.0, "parse_requirement": 1.0, "rank_joins": 2.0},
 "created_at": "2026-11-25T21:05:00Z", "updated_at": "2026-11-25T21:05:02Z"}
```
Run status values: `queued`, `profiling`, `ranking`, `awaiting_approval`, `generating`, `checking`, `repairing`, `completed`, `failed`. `parsed_requirement.source` is `llm` or `fallback` (keyword parsing when no model is available). `error` is set when `status` is `failed`.

`GET /runs/{run_id}/proposals` returns, recommended first:
```json
[{"edge_id": "e5", "from": "BSID.KUNNR", "to": "KNA1.KUNNR",
  "cardinality": "N:1", "normalization": "lpad_zeros:10", "fan_out_risk": false, "filter": null,
  "score": 0.932, "evidence_ids": ["ov_005", "ov_011", "uk_010", "uk_002"],
  "explanation": "97.0% of BSID.KUNNR values appear in KNA1.KUNNR after padding them with zeros to 10 characters (ov_005), and KNA1.KUNNR is unique (uk_010).",
  "explanation_source": "template", "relevance": "required", "recommended": true, "rescued": false,
  "status": "proposed", "rejection_reason": null, "decision_reason": null}]
```
- `cardinality` is `N:1`, `1:1`, `1:N` or `N:M`; only `N:1` and `1:1` joins can be recommended.
- `filter` is `{"column", "value", "choices"}` for attribute tables that would multiply rows (for example `MAKT.SPRAS = 'E'`).
- `explanation_source` is `llm` (checked against the evidence) or `template` (built from the evidence).
- `rescued` is true when the model recommended a join the scorer rejected only for a low score.
- `status` is `proposed`, `approved` or `rejected`.

`POST /runs/{run_id}/approvals` with `{"decisions": [{"edge_id": "e1", "action": "approve"}, {"edge_id": "e2", "action": "reject", "reason": "..."}]}` (1–200 decisions) returns 202 and the `Run`, which resumes in the background. Unknown edge ids give 422 (`details.edge_ids`); a run that is not `awaiting_approval` gives 409.

After approval the run generates one view per fact table and checks it (status `generating`, then `checking`). If nothing is approved, the run completes without views.

`GET /runs/{run_id}/views` returns:
```json
[{"name": "v_bsid", "sql": "CREATE OR REPLACE VIEW model.v_bsid AS SELECT ...", "dialect": "duckdb",
  "status": "created", "fact_table": "BSID", "joins": ["e5"],
  "derived_columns": ["due_date", "days_overdue", "aging_bucket"], "message": null}]
```
`status` is `created`, `repaired` or `failed` (with `message`). `joins` lists the approved edge ids the view uses. Add `?dialect=postgres`, `snowflake` or `bigquery` (default `duckdb`) to get the SQL translated with sqlglot; notes about anything that may need a manual change are in `message`.

`GET /runs/{run_id}/export?dialect=snowflake` returns the whole model as one `text/plain` SQL script (`Content-Disposition: attachment`), one `CREATE OR REPLACE VIEW` per created view, with notes as SQL comments. Unknown dialects give 422.

`GET /runs/{run_id}/checks` returns:
```json
[{"check_id": "v_bsid:orphan_keys:BSID.KUNNR", "view": "v_bsid", "kind": "orphan_keys",
  "passed": true, "observed": 40, "expected": 400,
  "message": "40 BSID.KUNNR values (0.50%) have no match in KNA1.KUNNR."}]
```
Check kinds: `row_count` (one view row per fact row), `fan_out` (no fact key twice), `orphan_keys` and `null_keys` (per join, within configured shares; `expected` is the allowed count), `bucket_coverage` (every open item in a known aging bucket), `reconciliation` (each money column sums to the fact table's total).

## Dashboard and questions
`GET /projects/{project_id}/dashboard` returns `{"metrics": [{"metric_id", "title", "sql", "chart": "bar", "data": []}]}`

`POST /projects/{project_id}/ask` with `{"question": "Which 5 customers have the most overdue receivables?"}` returns `{"sql", "rows", "chart", "evidence", "blocked": false, "reason_code": null}`

Reason codes for blocked questions: `UNSAFE_SQL`, `UNKNOWN_IDENTIFIER`, `TIMEOUT`, `LLM_UNAVAILABLE`.
