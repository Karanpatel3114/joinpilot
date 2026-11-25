# JoinPilot API contract

Version: 0.3. Change it only with the `contract-sync` skill, and bump the version.

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

`POST /projects/{project_id}/tables` takes either a multipart upload (field `files`, one or more CSV or Parquet files; maximum size `MAX_UPLOAD_MB` per file) or JSON `{"sample": "erp_s1_sap"}` (sample ids are `erp_<size><seed>_<naming>` with size `s` or `m` and naming `sap` or `friendly`). Returns 201 and `[TableSummary {table_id, name, row_count, column_count}]`. Uploading a file whose table name already exists replaces that table and keeps its `table_id`. CSV columns are typed so zero-padded ids stay text.

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

## Runs (agent)
`POST /projects/{project_id}/runs` with `{"requirement": "Open receivables by customer and aging bucket"}` returns `Run {run_id, status}`

Run status values: `queued`, `profiling`, `ranking`, `awaiting_approval`, `generating`, `checking`, `repairing`, `completed`, `failed`.

`GET /runs/{run_id}` returns `Run {run_id, status, requirement, parsed_requirement, error, timings_ms}`

`GET /runs/{run_id}/proposals` returns (planned; finalized in M4):
```json
[{"edge_id": "e1", "from": "VBAK.KUNNR", "to": "KNA1.KUNNR",
  "cardinality": "N:1", "normalization": "none", "fan_out_risk": false,
  "score": 0.94, "evidence_ids": ["ov_001", "uk_014"],
  "explanation": "Every order's customer number appears in the customer master (99.8% overlap, ov_001), and KNA1.KUNNR is unique (uk_014).",
  "status": "proposed"}]
```

`POST /runs/{run_id}/approvals` with `{"decisions": [{"edge_id": "e1", "action": "approve"}, {"edge_id": "e2", "action": "reject", "reason": "..."}]}` returns `Run` and resumes the run.

`GET /runs/{run_id}/views` returns `[View {name, sql, dialect, status}]`

`GET /runs/{run_id}/checks` returns `[CheckResult {check_id, view, kind, passed, observed, expected, message}]`

Check kinds: `row_count`, `fan_out`, `orphan_keys`, `null_keys`, `bucket_coverage`, `reconciliation`.

## Dashboard and questions
`GET /projects/{project_id}/dashboard` returns `{"metrics": [{"metric_id", "title", "sql", "chart": "bar", "data": []}]}`

`POST /projects/{project_id}/ask` with `{"question": "Which 5 customers have the most overdue receivables?"}` returns `{"sql", "rows", "chart", "evidence", "blocked": false, "reason_code": null}`

Reason codes for blocked questions: `UNSAFE_SQL`, `UNKNOWN_IDENTIFIER`, `TIMEOUT`, `LLM_UNAVAILABLE`.
