import { Search } from 'lucide-react'
import { useState } from 'react'
import { useGlossary } from '../api/hooks'
import { ErrorNote } from './ErrorNote'

/** Finds columns by business words, such as "customer name" for KNA1.NAME1. */
export function GlossarySearch({ projectId }: { projectId: string }) {
  const [draft, setDraft] = useState('')
  const [query, setQuery] = useState('')
  const matches = useGlossary(projectId, query)
  return (
    <div className="space-y-2">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          setQuery(draft)
        }}
        className="flex gap-2"
      >
        <label className="sr-only" htmlFor="glossary-query">
          Find columns by business words
        </label>
        <input
          id="glossary-query"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={200}
          placeholder="Find columns by business words, e.g. customer name"
          className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"
        />
        <button
          type="submit"
          className="btn-secondary"
        >
          <Search className="h-4 w-4" /> Search
        </button>
      </form>
      <ErrorNote error={matches.error} />
      {matches.data && (
        <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 dark:divide-slate-800 dark:border-slate-800">
          {matches.data.map((m) => (
            <li key={m.column} className="flex items-center justify-between gap-4 px-3 py-2 text-sm">
              <span>
                <span className="font-mono font-medium">{m.column}</span>
                <span className="ml-2 text-slate-500 dark:text-slate-400">{m.description}</span>
              </span>
              <span className="tabular-nums text-slate-500 dark:text-slate-400" title="Cosine similarity">
                {m.score.toFixed(2)}
              </span>
            </li>
          ))}
          {matches.data.length === 0 && <li className="px-3 py-2 text-sm text-slate-500 dark:text-slate-400">No match.</li>}
        </ul>
      )}
    </div>
  )
}
