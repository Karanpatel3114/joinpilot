import { useState } from 'react'
import type { Metric } from '../../types/api'
import { cell, label } from './chartTheme'
import { MetricChart } from './MetricChart'

/** One metric: its chart, what it means, and on request its rows and the SQL behind it. */
export function MetricCard({ metric }: { metric: Metric }) {
  const [show, setShow] = useState<'chart' | 'table' | 'sql'>('chart')
  const columns = [metric.x, ...metric.y]
  return (
    <article
      aria-label={metric.title}
      className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
    >
      <header className="flex flex-wrap items-start gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold">{metric.title}</h3>
          <p className="text-sm text-slate-600 dark:text-slate-400">{metric.description}</p>
        </div>
        {metric.requested && (
          <span className="rounded-full bg-brand-100 px-2 py-0.5 text-xs text-brand-700 dark:bg-slate-800 dark:text-brand-100">
            asked for
          </span>
        )}
      </header>
      {metric.status === 'failed' ? (
        <p role="alert" className="text-sm text-rose-700 dark:text-rose-300">
          {metric.message}
        </p>
      ) : (
        <>
          <div role="group" aria-label={`${metric.title} view`} className="flex gap-1 text-xs">
            {(['chart', 'table', 'sql'] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                aria-pressed={show === mode}
                onClick={() => setShow(mode)}
                className={`rounded-md px-2 py-1 ${
                  show === mode
                    ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
                }`}
              >
                {mode === 'sql' ? 'SQL' : mode === 'chart' ? 'Chart' : 'Table'}
              </button>
            ))}
          </div>
          {show === 'chart' &&
            (metric.data.length ? (
              <div role="img" aria-label={`${metric.title}: chart of ${metric.data.length} rows; the Table view lists every value.`}>
                <MetricChart metric={metric} />
              </div>
            ) : (
              <p className="text-sm text-slate-500 dark:text-slate-400">No rows match this metric.</p>
            ))}
          {show === 'table' && (
            <div className="max-h-72 overflow-auto rounded-lg border border-slate-200 dark:border-slate-800">
              <table aria-label={`${metric.title} data`} className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                  <tr>
                    {columns.map((c) => (
                      <th key={c} className="px-3 py-2">
                        {label(c)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {metric.data.map((row, i) => (
                    <tr key={i}>
                      {columns.map((c, j) => (
                        <td key={c} className={`px-3 py-1.5 ${j > 0 ? 'text-right tabular-nums' : ''}`}>
                          {cell(row[c])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {show === 'sql' && (
            <pre className="max-h-72 overflow-auto rounded-lg bg-slate-50 p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap dark:bg-slate-950">
              {metric.sql}
            </pre>
          )}
          <p className="text-xs text-slate-500 dark:text-slate-400">
            From view <span className="font-mono">{metric.view}</span>
          </p>
        </>
      )}
    </article>
  )
}
