import type { Overlap } from '../types/api'
import { EvidenceId } from './EvidenceId'
import { pct } from './format'

/** Value overlaps that start from one table: the evidence join candidates are built from. */
export function OverlapList({ table, overlaps }: { table: string; overlaps: Overlap[] }) {
  const mine = overlaps
    .filter((o) => o.from.startsWith(`${table}.`))
    .sort((a, b) => b.inclusion_ratio - a.inclusion_ratio)
  if (!mine.length) return <p className="text-sm text-slate-500">No overlaps from {table}.</p>
  return (
    <ul className="space-y-2">
      {mine.map((o) => (
        <li
          key={o.evidence_id}
          className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-800"
        >
          <EvidenceId id={o.evidence_id} />
          <span className="font-mono">
            {o.from} → {o.to}
          </span>
          <span className="font-semibold tabular-nums">{pct(o.inclusion_ratio)}</span>
          {o.normalization !== 'none' && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-300">
              {o.normalization} (raw {pct(o.raw_inclusion_ratio)})
            </span>
          )}
          {o.sampled && <span className="text-xs text-slate-500">sampled</span>}
        </li>
      ))}
    </ul>
  )
}
