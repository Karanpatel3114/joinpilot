import { AlertTriangle, ArrowLeft, LayoutDashboard } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { SETTLED, useProfile, useProposals, useRun } from '../api/hooks'
import { ApprovalList } from '../components/ApprovalList'
import { CheckResults } from '../components/CheckResults'
import { ErrorNote } from '../components/ErrorNote'
import { EvidencePanel } from '../components/EvidencePanel'
import { JoinGraph } from '../components/JoinGraph'
import { RunStatusBadge } from '../components/RunStatusBadge'
import { RunTimeline } from '../components/RunTimeline'
import { SqlViewer } from '../components/SqlViewer'
import type { RunStatus } from '../types/api'

/** Statuses before the ranking step has stored any proposals. */
const BEFORE_PROPOSALS: RunStatus[] = ['queued', 'profiling', 'ranking']

/** One run: live status, the proposed join graph with evidence, and approval. */
export function RunPage() {
  const { runId = '' } = useParams()
  const run = useRun(runId)
  const status = run.data?.status
  const ready = status !== undefined && !BEFORE_PROPOSALS.includes(status)
  const proposals = useProposals(runId, ready)
  const profile = useProfile(run.data?.project_id ?? '', Boolean(run.data))
  const [selected, setSelected] = useState<string | null>(null)
  if (!run.data) {
    if (run.error) return <ErrorNote error={run.error} />
    return <p className="text-sm text-slate-500 dark:text-slate-400">Loading run…</p>
  }
  const list = proposals.data ?? []
  const noCandidates = proposals.isSuccess && list.length === 0 && SETTLED.includes(run.data.status)
  return (
    <section className="space-y-6">
      <Link
        to={`/projects/${run.data.project_id}`}
        className="inline-flex items-center gap-1 text-sm text-slate-500 dark:text-slate-400 hover:text-brand-600 dark:hover:text-brand-300"
      >
        <ArrowLeft className="h-4 w-4" /> Back to project
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Run</h1>
          <p className="mt-1 max-w-3xl text-slate-600 dark:text-slate-400">{run.data.requirement}</p>
        </div>
        <RunStatusBadge status={run.data.status} />
      </div>
      <RunTimeline run={run.data} />
      {run.error && <ErrorNote error={run.error} />}
      {run.data.error && <ErrorNote error={new Error(run.data.error)} />}
      {run.data.warnings.length > 0 && (
        <ul aria-label="Warnings" className="space-y-1 text-sm text-amber-800 dark:text-amber-300">
          {run.data.warnings.map((w, i) => (
            <li key={`${i}:${w}`} className="flex gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {w}
            </li>
          ))}
        </ul>
      )}
      {noCandidates && (
        <p className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-600 dark:border-slate-700 dark:text-slate-400">
          No join candidates were found between these tables, so there is nothing to approve. Check
          that the key columns share values, or add the tables that connect them.
        </p>
      )}
      {list.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
          <JoinGraph proposals={list} selected={selected} onSelect={setSelected} />
          <EvidencePanel proposal={list.find((p) => p.edge_id === selected)} profile={profile.data} />
        </div>
      )}
      {list.length > 0 && (
        <ApprovalList
          key={run.data.status}
          runId={runId}
          proposals={list}
          editable={run.data.status === 'awaiting_approval'}
          selected={selected}
          onSelect={setSelected}
        />
      )}
      {run.data.status === 'completed' && list.some((p) => p.status === 'approved') && (
        <>
          <Link
            to={`/projects/${run.data.project_id}?tab=Dashboard`}
            className="btn-primary"
          >
            <LayoutDashboard className="h-4 w-4" /> Open the KPI dashboard
          </Link>
          <SqlViewer runId={runId} />
          <CheckResults runId={runId} />
        </>
      )}
    </section>
  )
}
