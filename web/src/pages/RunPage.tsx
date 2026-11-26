import { AlertTriangle, ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { SETTLED, useProfile, useProposals, useRun } from '../api/hooks'
import { ApprovalList } from '../components/ApprovalList'
import { ErrorNote } from '../components/ErrorNote'
import { EvidencePanel } from '../components/EvidencePanel'
import { JoinGraph } from '../components/JoinGraph'
import { RunStatusBadge } from '../components/RunStatusBadge'
import { RunTimeline } from '../components/RunTimeline'

/** One run: live status, the proposed join graph with evidence, and approval. */
export function RunPage() {
  const { runId = '' } = useParams()
  const run = useRun(runId)
  const status = run.data?.status
  const ready = status ? SETTLED.includes(status) || status === 'generating' : false
  const proposals = useProposals(runId, ready)
  const profile = useProfile(run.data?.project_id ?? '', Boolean(run.data))
  const [selected, setSelected] = useState<string | null>(null)
  if (run.error) return <ErrorNote error={run.error} />
  if (!run.data) return <p className="text-sm text-slate-500">Loading run…</p>
  const list = proposals.data ?? []
  return (
    <section className="space-y-6">
      <Link
        to={`/projects/${run.data.project_id}`}
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-brand-600"
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
      {run.data.error && <ErrorNote error={new Error(run.data.error)} />}
      {run.data.warnings.length > 0 && (
        <ul aria-label="Warnings" className="space-y-1 text-sm text-amber-800 dark:text-amber-300">
          {run.data.warnings.map((w) => (
            <li key={w} className="flex gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {w}
            </li>
          ))}
        </ul>
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
    </section>
  )
}
