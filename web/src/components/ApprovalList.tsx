import { useState } from 'react'
import { useApprove } from '../api/hooks'
import type { Decision, Proposal } from '../types/api'
import { ErrorNote } from './ErrorNote'
import { pct } from './format'

/** Every proposed join with an approve or reject choice; recommended joins start approved. */
export function ApprovalList({
  runId,
  proposals,
  editable,
  selected,
  onSelect,
}: {
  runId: string
  proposals: Proposal[]
  editable: boolean
  selected: string | null
  onSelect: (edgeId: string) => void
}) {
  const [choices, setChoices] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(proposals.map((p) => [p.edge_id, p.recommended])),
  )
  const approve = useApprove(runId)
  const [expanded, setExpanded] = useState(false)
  const approvedCount = Object.values(choices).filter(Boolean).length
  const main = proposals.filter((p) => p.recommended || p.status === 'approved')
  const others = proposals.filter((p) => !main.includes(p))
  const visible = expanded ? proposals : main

  function submit() {
    const decisions: Decision[] = proposals.map((p) => ({
      edge_id: p.edge_id,
      action: choices[p.edge_id] ? 'approve' : 'reject',
    }))
    approve.mutate(decisions)
  }

  return (
    <div className="space-y-3">
      <ul aria-label="Proposed joins" className="divide-y divide-slate-200 rounded-xl border border-slate-200 dark:divide-slate-800 dark:border-slate-800">
        {visible.map((p) => (
          <li key={p.edge_id} className="flex items-center gap-3 px-3 py-2 text-sm">
            {editable ? (
              <input
                type="checkbox"
                checked={choices[p.edge_id] ?? false}
                onChange={(e) => setChoices((c) => ({ ...c, [p.edge_id]: e.target.checked }))}
                aria-label={`Approve ${p.edge_id} ${p.from} to ${p.to}`}
                className="h-4 w-4 accent-brand-600"
              />
            ) : (
              <span className="w-16 text-xs font-medium uppercase text-slate-500">{p.status}</span>
            )}
            <button
              type="button"
              onClick={() => onSelect(p.edge_id)}
              aria-pressed={selected === p.edge_id}
              className="flex-1 text-left font-mono hover:text-brand-600"
            >
              {p.edge_id} {p.from} → {p.to}
            </button>
            <span className="tabular-nums text-slate-500">{pct(p.score)}</span>
            {p.recommended && (
              <span className="rounded-full bg-brand-100 px-2 py-0.5 text-xs text-brand-700 dark:bg-slate-800 dark:text-brand-100">
                recommended
              </span>
            )}
          </li>
        ))}
      </ul>
      {others.length > 0 && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="text-sm text-brand-600 hover:underline"
        >
          {expanded ? 'Hide' : 'Show'} {others.length} other candidates the scorer did not recommend
        </button>
      )}
      {editable && (
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={submit}
            disabled={approve.isPending}
            className="rounded-lg bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            Approve {approvedCount} {approvedCount === 1 ? 'join' : 'joins'} and build the model
          </button>
          <span className="text-sm text-slate-500">Nothing is built until you approve.</span>
        </div>
      )}
      <ErrorNote error={approve.error} />
    </div>
  )
}
