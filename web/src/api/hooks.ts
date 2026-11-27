import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type {
  Answer,
  CheckResult,
  Dashboard,
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
import { ApiRequestError, getJson, postFiles, postJson } from './client'
import { isUnreachable } from './errorMessage'

/** Statuses after which a run no longer changes without a person acting. */
export const SETTLED: RunStatus[] = ['awaiting_approval', 'completed', 'failed']

/**
 * The next poll after the last refresh: on schedule when it worked; never after an
 * answer that will not change by waiting (404, 409, 422); after the server's
 * Retry-After on 429; and gently while the API is down or waking up.
 */
export function nextPoll(error: unknown, interval: number): number | false {
  if (!error) return interval
  if (error instanceof ApiRequestError) {
    if (error.status === 429) return Math.max(Number(error.details.retry_after_seconds) || 30, 1) * 1000
    if (error.status < 500) return false
  }
  return Math.max(interval, 10_000)
}

/**
 * Retry a failed read only while the API is unreachable (down or waking up): a free
 * server's cold start takes about a minute, which six retries with the default doubling
 * delay (1 s to 30 s) cover. Any answer from the API itself, even a 500, is final.
 */
export function shouldRetry(failures: number, error: unknown): boolean {
  return isUnreachable(error) && failures < 6
}

export const keys = {
  projects: ['projects'] as const,
  profile: (id: string) => ['profile', id] as const,
  runs: (id: string) => ['runs', id] as const,
  run: (id: string) => ['run', id] as const,
  proposals: (id: string) => ['proposals', id] as const,
  views: (id: string, dialect: SqlDialect) => ['views', id, dialect] as const,
  checks: (id: string) => ['checks', id] as const,
  glossary: (id: string, q: string) => ['glossary', id, q] as const,
  dashboard: (id: string) => ['dashboard', id] as const,
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
    void client.invalidateQueries({ queryKey: ['glossary', projectId] })
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

/** A project's runs, refreshed every few seconds while any of them is still working. */
export function useRuns(projectId: string) {
  return useQuery({
    queryKey: keys.runs(projectId),
    queryFn: () => getJson<Run[]>(`/projects/${projectId}/runs`),
    refetchInterval: (query) =>
      query.state.data?.some((r) => !SETTLED.includes(r.status)) ? nextPoll(query.state.error, 3000) : false,
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

/** A run, polled every second until it settles. A run that never loaded (an unknown id or
 * an API that is down) is not polled; after a failed poll, see `nextPoll`. */
export function useRun(runId: string) {
  return useQuery({
    queryKey: keys.run(runId),
    queryFn: () => getJson<Run>(`/runs/${runId}`),
    refetchInterval: (query) => {
      const { data, status } = query.state
      if (!data) return status === 'error' ? false : 1000
      return SETTLED.includes(data.status) ? false : nextPoll(query.state.error, 1000)
    },
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
    onSuccess: (run) => {
      // The response already says "generating", so the button cannot be pressed twice.
      client.setQueryData(keys.run(runId), run)
      void client.invalidateQueries({ queryKey: keys.proposals(runId) })
      void client.invalidateQueries({ queryKey: keys.runs(run.project_id) })
    },
  })
}

export function useViews(runId: string, dialect: SqlDialect) {
  return useQuery({
    queryKey: keys.views(runId, dialect),
    queryFn: () => getJson<View[]>(`/runs/${runId}/views?dialect=${dialect}`),
    placeholderData: (previous) => previous,
  })
}

export function useChecks(runId: string) {
  return useQuery({
    queryKey: keys.checks(runId),
    queryFn: () => getJson<CheckResult[]>(`/runs/${runId}/checks`),
  })
}

export function useDashboard(projectId: string) {
  return useQuery({
    queryKey: keys.dashboard(projectId),
    queryFn: () => getJson<Dashboard>(`/projects/${projectId}/dashboard`),
  })
}

export function useAsk(projectId: string) {
  return useMutation({
    mutationFn: (question: string) => postJson<Answer>(`/projects/${projectId}/ask`, { question }),
  })
}
