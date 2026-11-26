import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type {
  CheckResult,
  Decision,
  GlossaryMatch,
  Project,
  ProjectProfile,
  Proposal,
  Run,
  RunStatus,
  SqlDialect,
  TableSummary,
  View,
} from '../types/api'
import { getJson, postFiles, postJson } from './client'

/** Statuses after which a run no longer changes without a person acting. */
export const SETTLED: RunStatus[] = ['awaiting_approval', 'completed', 'failed']

export const keys = {
  projects: ['projects'] as const,
  profile: (id: string) => ['profile', id] as const,
  runs: (id: string) => ['runs', id] as const,
  run: (id: string) => ['run', id] as const,
  proposals: (id: string) => ['proposals', id] as const,
  views: (id: string, dialect: SqlDialect) => ['views', id, dialect] as const,
  checks: (id: string) => ['checks', id] as const,
  glossary: (id: string, q: string) => ['glossary', id, q] as const,
}

export function useProjects() {
  return useQuery({ queryKey: keys.projects, queryFn: () => getJson<Project[]>('/projects') })
}

export function useCreateProject() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => postJson<Project>('/projects', { name }),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.projects }),
  })
}

function useTablesChanged(projectId: string) {
  const client = useQueryClient()
  return () => {
    void client.invalidateQueries({ queryKey: keys.projects })
    void client.invalidateQueries({ queryKey: keys.profile(projectId) })
  }
}

export function useLoadSample(projectId: string) {
  const onSuccess = useTablesChanged(projectId)
  return useMutation({
    mutationFn: (sample: string) =>
      postJson<TableSummary[]>(`/projects/${projectId}/tables`, { sample }),
    onSuccess,
  })
}

export function useUploadFiles(projectId: string) {
  const onSuccess = useTablesChanged(projectId)
  return useMutation({
    mutationFn: (files: File[]) => postFiles<TableSummary[]>(`/projects/${projectId}/tables`, files),
    onSuccess,
  })
}

export function useProfile(projectId: string, enabled = true) {
  return useQuery({
    queryKey: keys.profile(projectId),
    queryFn: () => getJson<ProjectProfile>(`/projects/${projectId}/profile`),
    enabled,
  })
}

export function useGlossary(projectId: string, q: string) {
  return useQuery({
    queryKey: keys.glossary(projectId, q),
    queryFn: () =>
      getJson<GlossaryMatch[]>(`/projects/${projectId}/glossary?q=${encodeURIComponent(q)}&k=5`),
    enabled: q.trim().length > 0,
  })
}

export function useRuns(projectId: string) {
  return useQuery({
    queryKey: keys.runs(projectId),
    queryFn: () => getJson<Run[]>(`/projects/${projectId}/runs`),
  })
}

export function useStartRun(projectId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (requirement: string) =>
      postJson<Run>(`/projects/${projectId}/runs`, { requirement }),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.runs(projectId) }),
  })
}

/** A run, polled every second until it settles. */
export function useRun(runId: string) {
  return useQuery({
    queryKey: keys.run(runId),
    queryFn: () => getJson<Run>(`/runs/${runId}`),
    refetchInterval: (query) =>
      query.state.data && SETTLED.includes(query.state.data.status) ? false : 1000,
  })
}

export function useProposals(runId: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.proposals(runId),
    queryFn: () => getJson<Proposal[]>(`/runs/${runId}/proposals`),
    enabled,
  })
}

export function useApprove(runId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (decisions: Decision[]) => postJson<Run>(`/runs/${runId}/approvals`, { decisions }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.run(runId) })
      void client.invalidateQueries({ queryKey: keys.proposals(runId) })
    },
  })
}

export function useViews(runId: string, dialect: SqlDialect, enabled: boolean) {
  return useQuery({
    queryKey: keys.views(runId, dialect),
    queryFn: () => getJson<View[]>(`/runs/${runId}/views?dialect=${dialect}`),
    enabled,
  })
}

export function useChecks(runId: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.checks(runId),
    queryFn: () => getJson<CheckResult[]>(`/runs/${runId}/checks`),
    enabled,
  })
}
