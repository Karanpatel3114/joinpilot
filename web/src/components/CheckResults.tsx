import { CircleCheck, CircleX } from 'lucide-react'
import { useChecks } from '../api/hooks'
import { ErrorNote } from './ErrorNote'

const KIND_LABELS: Record<string, string> = {
  row_count: 'Row count',
  fan_out: 'Fan-out',
  orphan_keys: 'Orphan keys',
  null_keys: 'Null keys',
  bucket_coverage: 'Bucket coverage',
  reconciliation: 'Reconciliation',
}

/** The automated checks on every view, with observed and expected values. */
export function CheckResults({ runId }: { runId: string }) {
  const checks = useChecks(runId, true)
  const results = checks.data ?? []
  const passed = results.filter((c) => c.passed).length
  return (
    <section aria-label="Check results" className="space-y-3">
      <h2 className="text-lg font-semibold">
        Checks{' '}
        {results.length > 0 && (
          <span className={passed === results.length ? 'text-emerald-600' : 'text-rose-600'}>
            {passed} of {results.length} passed
          </span>
        )}
      </h2>
      <ErrorNote error={checks.error} />
      <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-900">
            <tr>
              <th className="px-3 py-2">Result</th>
              <th className="px-3 py-2">View</th>
              <th className="px-3 py-2">Check</th>
              <th className="px-3 py-2 text-right">Observed</th>
              <th className="px-3 py-2 text-right">Expected</th>
              <th className="px-3 py-2">What it means</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {results.map((c) => (
              <tr key={c.check_id}>
                <td className="px-3 py-2">
                  {c.passed ? (
                    <CircleCheck className="h-4 w-4 text-emerald-600" aria-label="passed" />
                  ) : (
                    <CircleX className="h-4 w-4 text-rose-600" aria-label="failed" />
                  )}
                </td>
                <td className="px-3 py-2 font-mono">{c.view}</td>
                <td className="px-3 py-2">{KIND_LABELS[c.kind] ?? c.kind}</td>
                <td className="px-3 py-2 text-right tabular-nums">{String(c.observed ?? '')}</td>
                <td className="px-3 py-2 text-right tabular-nums">{String(c.expected ?? '')}</td>
                <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{c.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
