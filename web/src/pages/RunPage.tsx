import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { SETTLED, useProfile, useProposals, useRun } from '../api/hooks'
import { ErrorNote } from '../components/ErrorNote'
import { EvidencePanel } from '../components/EvidencePanel'
import { JoinGraph } from '../components/JoinGraph'
import { pct } from '../components/format'

/** One run: the proposed join graph with its evidence. */
export function RunPage() {
  const { runId = '' } = useParams()
  const run = useRun(runId)
  const ready = run.data ? SETTLED.includes(run.data.status) : false
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
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Run</h1>
        <p className="mt-1 text-slate-600 dark:text-slate-400">{run.data.requirement}</p>
      </div>
      {list.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
          <JoinGraph proposals={list} selected={selected} onSelect={setSelected} />
          <EvidencePanel proposal={list.find((p) => p.edge_id === selected)} profile={profile.data} />
        </div>
      )}
      {list.length > 0 && (
        <ul aria-label="Proposed joins" className="space-y-1">
          {list.map((p) => (
            <li key={p.edge_id}>
              <button
                type="button"
                onClick={() => setSelected(p.edge_id)}
                aria-pressed={selected === p.edge_id}
                className="w-full rounded-lg px-3 py-2 text-left font-mono text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                {p.edge_id} {p.from} → {p.to} · {pct(p.score)}
                {p.recommended ? ' · recommended' : ''}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
