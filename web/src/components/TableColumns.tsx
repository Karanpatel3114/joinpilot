import { KeyRound } from 'lucide-react'
import type { KeyEvidence, TableProfile } from '../types/api'
import { EvidenceId } from './EvidenceId'
import { count, pct } from './format'

/** Column statistics of one table, with the uniqueness evidence behind each key. */
export function TableColumns({ table, keys }: { table: TableProfile; keys: KeyEvidence[] }) {
  const uniqueness = new Map(
    keys.filter((k) => k.table === table.name && k.columns.length === 1).map((k) => [k.columns[0], k]),
  )
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">Columns of {table.name}</caption>
        <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-900">
          <tr>
            <th className="px-3 py-2">Column</th>
            <th className="px-3 py-2">Type</th>
            <th className="px-3 py-2 text-right">Nulls</th>
            <th className="px-3 py-2 text-right">Distinct</th>
            <th className="px-3 py-2">Uniqueness</th>
            <th className="px-3 py-2">Examples</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {table.columns.map((c) => {
            const key = uniqueness.get(c.name)
            return (
              <tr key={c.name}>
                <td className="px-3 py-2 font-mono font-medium">
                  <span className="inline-flex items-center gap-1">
                    {c.is_key_candidate && (
                      <KeyRound className="h-3.5 w-3.5 text-amber-500" aria-label="Key candidate" />
                    )}
                    {c.name}
                  </span>
                </td>
                <td className="px-3 py-2 text-slate-500">{c.type}</td>
                <td className="px-3 py-2 text-right tabular-nums">{pct(c.null_pct)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{count(c.distinct_count)}</td>
                <td className="px-3 py-2">
                  {key ? (
                    <span className="inline-flex items-center gap-2">
                      {pct(key.uniqueness)} <EvidenceId id={key.evidence_id} />
                    </span>
                  ) : (
                    <span className="text-slate-400">n/a</span>
                  )}
                </td>
                <td className="max-w-xs truncate px-3 py-2 font-mono text-xs text-slate-500">
                  {c.sample_values.slice(0, 3).join(', ')}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
