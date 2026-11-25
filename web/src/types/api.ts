// Types for the JoinPilot API. They mirror docs/contract.md (version 0.2) exactly.
// Change them only together with the contract, the Pydantic schemas and the fixtures.

export type ErrorCode =
  | 'NOT_FOUND'
  | 'INVALID_INPUT'
  | 'CONFLICT'
  | 'PAYLOAD_TOO_LARGE'
  | 'INTERNAL_ERROR'

export interface ApiError {
  error: {
    code: ErrorCode | string
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

/** `none`, `lpad_zeros:<width>`, `strip_leading_zeros` or `trim_upper`. */
export type Normalization = string

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
