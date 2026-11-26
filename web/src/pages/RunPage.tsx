import { AlertTriangle, LayoutDashboard } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { SETTLED, useProfile, useProposals, useRun } from '../api/hooks'
import { ApprovalList } from '../components/ApprovalList'
import { CheckResults } from '../components/CheckResults'
import { ErrorNote } from '../components/ErrorNote'
import { EvidencePanel } from '../components/EvidencePanel'
import { JoinGraph } from '../components/JoinGraph'
import { PageHeader } from '../components/PageHeader'
import { RunStatusBadge } from '../components/RunStatusBadge'
import { RunTimeline } from '../components/RunTimeline'
import { SqlViewer } from '../components/SqlViewer'
import type { RunStatus } from '../types/api'

/** Statuses before the ranking step has stored any proposals. */
const BEFORE_PROPOSALS: RunStatus[] = ['queued', 'profiling', 'ranking']

/** The run page's headline for each status, in plain words. */
const HEADLINES: Record<RunStatus, string> = {
  queued: 'Queued',
  profiling: 'Profiling the tables',
  ranking: 'Ranking the joins',
  awaiting_approval: 'Waiting for your approval',
  generating: 'Generating views',
  checking: 'Running checks',
  repairing: 'Repairing views',
  completed: 'Model ready',
  failed: 'Run failed',
}

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
    <section className="space-y-8">
      <PageHeader
        back={{ to: `/projects/${run.data.project_id}?tab=Runs`, label: 'Back to project' }}
        eyebrow="Agent run"
        title={HEADLINES[run.data.status]}
        aside={<RunStatusBadge status={run.data.status} />}
      >
        <p className="max-w-3xl text-[17px] leading-relaxed text-slate-600 dark:text-slate-300">{run.data.requirement}</p>
      </PageHeader>
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
