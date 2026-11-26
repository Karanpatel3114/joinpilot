// Types for the JoinPilot API. They mirror docs/contract.md (version 0.6) exactly.
// Change them only together with the contract, the Pydantic schemas and the fixtures.

export type ErrorCode =
  | 'NOT_FOUND'
  | 'INVALID_INPUT'
  | 'CONFLICT'
  | 'PAYLOAD_TOO_LARGE'
  | 'INTERNAL_ERROR'

export interface ApiError {
  error: {
    // Known codes keep autocompletion; unknown future codes are still accepted.
    code: ErrorCode | (string & {})
    message: string
    details: Record<string, unknown>
  }
}

export interface HealthResponse {
  status: 'ok'
  version: string
}

export interface Project {
  id: string
  name: string
  created_at: string
  table_count: number
}

export interface CreateProjectRequest {
  name: string
}

export interface SampleRequest {
  sample: string
}

export interface TableSummary {
  table_id: string
  name: string
  row_count: number
  column_count: number
}

export interface ColumnProfile {
  name: string
  type: string
  null_pct: number
  non_null_count: number
  distinct_count: number
  sample_values: string[]
  is_key_candidate: boolean
  min_value: string | null
  max_value: string | null
  max_length: number | null
  fixed_length: number | null
  digits_only: boolean
}

export interface TableProfile {
  table_id: string
  name: string
  row_count: number
  columns: ColumnProfile[]
  candidate_keys: string[][]
}

export interface KeyEvidence {
  evidence_id: string
  table: string
  columns: string[]
  distinct_count: number
  non_null_count: number
  uniqueness: number
}

export type Normalization =
  | 'none'
  | 'strip_leading_zeros'
  | 'trim_upper'
  | `lpad_zeros:${number}`

export interface Overlap {
  evidence_id: string
  from: string
  to: string
  inclusion_ratio: number
  raw_inclusion_ratio: number
  normalization: Normalization
  checked_values: number
  matched_values: number
  sampled: boolean
}

export interface ProjectProfile {
  tables: TableProfile[]
  keys: KeyEvidence[]
  overlaps: Overlap[]
}

export type RunStatus =
  | 'queued'
  | 'profiling'
  | 'ranking'
  | 'awaiting_approval'
  | 'generating'
  | 'checking'
  | 'repairing'
  | 'completed'
  | 'failed'

export interface CreateRunRequest {
  requirement: string
}

export interface Measure {
  name: string
  description: string
}

export interface RequirementFilter {
  field: string
  operator: '=' | '!=' | '>' | '>=' | '<' | '<=' | 'between' | 'in'
  value: string
}

export interface ParsedRequirement {
  summary: string
  entities: string[]
  measures: Measure[]
  dimensions: string[]
  filters: RequirementFilter[]
  relevant_tables: string[]
  source: 'llm' | 'fallback'
}

export interface Run {
  run_id: string
  project_id: string
  status: RunStatus
  requirement: string
  parsed_requirement: ParsedRequirement | null
  error: string | null
  warnings: string[]
  timings_ms: Record<string, number>
  created_at: string
  updated_at: string
}

export type Cardinality = 'N:1' | '1:1' | '1:N' | 'N:M'

export interface JoinFilter {
  column: string
  value: string
  choices: string[]
}

export interface Proposal {
  edge_id: string
  from: string
  to: string
  cardinality: Cardinality
  normalization: Normalization
  fan_out_risk: boolean
  filter: JoinFilter | null
  score: number
  evidence_ids: string[]
  explanation: string
  explanation_source: 'llm' | 'template'
  relevance: 'required' | 'useful' | 'not_needed'
  recommended: boolean
  rescued: boolean
  status: 'proposed' | 'approved' | 'rejected'
  rejection_reason: string | null
  decision_reason: string | null
}

export interface Decision {
  edge_id: string
  action: 'approve' | 'reject'
  reason?: string | null
}

export interface ApprovalRequest {
  decisions: Decision[]
}

export interface GlossaryMatch {
  column: string
  description: string
  score: number
}

export interface View {
  name: string
  sql: string
  dialect: string
  status: 'created' | 'repaired' | 'failed'
  fact_table: string
  joins: string[]
  derived_columns: string[]
  message: string | null
}

export type CheckKind =
  | 'row_count'
  | 'fan_out'
  | 'orphan_keys'
  | 'null_keys'
  | 'bucket_coverage'
  | 'reconciliation'

export interface CheckResult {
  check_id: string
  view: string
  kind: CheckKind
  passed: boolean
  observed: number | string | null
  expected: number | string | null
  message: string
}
