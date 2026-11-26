import { Check, Copy, Download } from 'lucide-react'
import { useState } from 'react'
import { API_URL } from '../api/client'
import { useViews } from '../api/hooks'
import type { SqlDialect } from '../types/api'
import { ErrorNote } from './ErrorNote'

const DIALECTS: { value: SqlDialect; label: string }[] = [
  { value: 'duckdb', label: 'DuckDB' },
  { value: 'postgres', label: 'Postgres' },
  { value: 'snowflake', label: 'Snowflake' },
  { value: 'bigquery', label: 'BigQuery' },
]

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard
          ?.writeText(text)
          .then(() => {
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
          })
          .catch(() => setCopied(false))
      }}
      className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

/** The generated views' SQL in the chosen warehouse dialect, with copy and download. */
export function SqlViewer({ runId }: { runId: string }) {
  const [dialect, setDialect] = useState<SqlDialect>('duckdb')
  const views = useViews(runId, dialect)
  return (
    <section aria-label="Generated SQL" className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold">Generated views</h2>
        <label className="ml-auto flex items-center gap-2 text-sm">
          Dialect
          <select
            value={dialect}
            onChange={(e) => setDialect(e.target.value as SqlDialect)}
            className="rounded-lg border border-slate-300 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
          >
            {DIALECTS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
        </label>
        <a
          href={`${API_URL}/runs/${runId}/export?dialect=${dialect}`}
          className="inline-flex items-center gap-1 rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700"
        >
          <Download className="h-4 w-4" /> Download SQL
        </a>
      </div>
      <ErrorNote error={views.error} />
      {views.isFetching && views.isPlaceholderData && (
        <p className="text-sm text-slate-500 dark:text-slate-400">Translating to {dialect}…</p>
      )}
      {views.data?.map((view) => (
        <article key={view.name} className="rounded-xl border border-slate-200 dark:border-slate-800">
          <header className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-3 py-2 text-sm dark:border-slate-800">
            <span className="font-mono font-semibold">{view.name}</span>
            <span className="text-slate-500 dark:text-slate-400">from {view.fact_table}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-xs ${
                view.status === 'failed'
                  ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                  : view.status === 'repaired'
                    ? 'bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-300'
                    : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
              }`}
            >
              {view.status}
            </span>
            {view.derived_columns.length > 0 && (
              <span className="text-xs text-slate-500 dark:text-slate-400">derived: {view.derived_columns.join(', ')}</span>
            )}
            <span className="ml-auto">
              <CopyButton text={view.sql} />
            </span>
          </header>
          {view.message && <p className="px-3 pt-2 text-xs text-amber-700 dark:text-amber-300">{view.message}</p>}
          <pre className="max-h-80 overflow-auto p-3 font-mono text-xs leading-relaxed">{view.sql}</pre>
        </article>
      ))}
    </section>
  )
}
