import type { KeyEvidence, Overlap, ProjectProfile, Proposal } from '../types/api'
import { EvidenceId } from './EvidenceId'
import { count, pct } from './format'

function describe(id: string, profile: ProjectProfile | undefined): string | null {
  const overlap: Overlap | undefined = profile?.overlaps.find((o) => o.evidence_id === id)
  if (overlap) {
    const norm = overlap.normalization === 'none' ? '' : ` after ${overlap.normalization}`
    return `${pct(overlap.inclusion_ratio)} of ${overlap.from} values found in ${overlap.to}${norm} (${count(overlap.matched_values)} of ${count(overlap.checked_values)} checked)`
  }
  const key: KeyEvidence | undefined = profile?.keys.find((k) => k.evidence_id === id)
  if (key) {
    return `${key.table}.(${key.columns.join(', ')}) is ${pct(key.uniqueness)} unique (${count(key.distinct_count)} distinct of ${count(key.non_null_count)})`
  }
  return null
}

/** Why a join is proposed: the explanation and the numbers behind every cited evidence id. */
export function EvidencePanel({
  proposal,
  profile,
}: {
  proposal: Proposal | undefined
  profile: ProjectProfile | undefined
}) {
  if (!proposal) {
    return (
      <aside className="rounded-xl border border-slate-200 p-4 text-sm text-slate-500 dark:border-slate-800">
        Select a join in the graph or the list to see its evidence.
      </aside>
    )
  }
  return (
    <aside
      aria-label="Evidence"
      className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 text-sm dark:border-slate-800 dark:bg-slate-900"
    >
      <h3 className="font-mono font-semibold">
        {proposal.edge_id}: {proposal.from} → {proposal.to}
      </h3>
      <div className="flex flex-wrap gap-2 text-xs">
        <span className="rounded-full bg-slate-100 px-2 py-0.5 dark:bg-slate-800">{proposal.cardinality}</span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 dark:bg-slate-800">score {pct(proposal.score)}</span>
        {proposal.normalization !== 'none' && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
            {proposal.normalization}
          </span>
        )}
        {proposal.fan_out_risk && (
          <span className="rounded-full bg-rose-100 px-2 py-0.5 text-rose-800 dark:bg-rose-950 dark:text-rose-300">
            fan-out risk
          </span>
        )}
        <span className="rounded-full bg-slate-100 px-2 py-0.5 dark:bg-slate-800">
          explained by {proposal.explanation_source === 'llm' ? 'the model (checked)' : 'template'}
        </span>
      </div>
      <p>{proposal.explanation}</p>
      {proposal.filter && (
        <p>
          Filter: <code className="font-mono">{proposal.filter.column} = '{proposal.filter.value}'</code>{' '}
          <span className="text-slate-500">(choices: {proposal.filter.choices.join(', ')})</span>
        </p>
      )}
      {proposal.rejection_reason && <p className="text-slate-500">Not recommended: {proposal.rejection_reason}.</p>}
      <ul className="space-y-1">
        {proposal.evidence_ids.map((id) => (
          <li key={id} className="flex items-start gap-2">
            <EvidenceId id={id} />
            <span className="text-slate-600 dark:text-slate-400">{describe(id, profile) ?? 'evidence'}</span>
          </li>
        ))}
      </ul>
    </aside>
  )
}
