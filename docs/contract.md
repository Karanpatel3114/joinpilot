# JoinPilot API contract

Version: 0.1 (draft). Change it only with the `contract-sync` skill, and bump the version.

All responses are JSON. Errors use `{"error": {"code": "STRING_CODE", "message": "plain-language message", "details": {}}}`. IDs are UUID strings. Times are ISO 8601 in UTC.

## Health
`GET /health` returns `{"status": "ok", "version": "0.1.0"}`

## Projects and tables
`POST /projects` with `{"name": "Demo ERP"}` returns `Project {id, name, created_at, table_count}`

`GET /projects` returns `[Project]`

`POST /projects/{project_id}/tables` takes a multipart upload (CSV or Parquet; maximum size from config), or `{"sample": "erp_s1_sap"}`. Returns `[TableSummary {table_id, name, row_count, column_count}]`

`GET /projects/{project_id}/profile` returns:
```json
{
  "tables": [{"table_id": "...", "name": "VBAK", "row_count": 5000,
    "columns": [{"name": "KUNNR", "type": "VARCHAR", "null_pct": 0.0,
      "distinct_count": 812, "sample_values": ["0000012345"], "is_key_candidate": false}],
    "candidate_keys": [["VBELN"]]}],
  "overlaps": [{"evidence_id": "ov_001", "from": "VBAK.KUNNR", "to": "KNA1.KUNNR",
    "inclusion_ratio": 0.998, "normalization": "none"}]
}
```

## Runs (agent)
`POST /projects/{project_id}/runs` with `{"requirement": "Open receivables by customer and aging bucket"}` returns `Run {run_id, status}`

Run status values: `queued`, `profiling`, `ranking`, `awaiting_approval`, `generating`, `checking`, `repairing`, `completed`, `failed`.

`GET /runs/{run_id}` returns `Run {run_id, status, requirement, parsed_requirement, error, timings_ms}`

`GET /runs/{run_id}/proposals` returns:
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
