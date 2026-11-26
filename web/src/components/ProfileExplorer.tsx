import { useState } from 'react'
import { useProfile } from '../api/hooks'
import { ErrorNote } from './ErrorNote'
import { GlossarySearch } from './GlossarySearch'
import { OverlapList } from './OverlapList'
import { TableColumns } from './TableColumns'
import { count } from './format'

/** Browse every table's columns, keys and overlaps, and search columns by business words. */
export function ProfileExplorer({ projectId }: { projectId: string }) {
  const profile = useProfile(projectId)
  const [selected, setSelected] = useState<string | null>(null)
  if (profile.isLoading) return <p className="text-sm text-slate-500">Profiling tables…</p>
  if (profile.error) return <ErrorNote error={profile.error} />
  const tables = profile.data?.tables ?? []
  if (!tables.length) return <p className="text-sm text-slate-500">Add tables to see their profile.</p>
  const current = tables.find((t) => t.name === selected) ?? tables[0]
  return (
    <div className="space-y-4">
      <GlossarySearch projectId={projectId} />
      <div className="grid gap-4 lg:grid-cols-[14rem_1fr]">
        <nav aria-label="Tables">
          <ul className="space-y-1">
            {tables.map((t) => (
              <li key={t.table_id}>
                <button
                  type="button"
                  onClick={() => setSelected(t.name)}
                  aria-current={t.name === current.name ? 'true' : undefined}
                  className={`w-full rounded-lg px-3 py-2 text-left text-sm ${
                    t.name === current.name
                      ? 'bg-brand-600 text-white'
                      : 'hover:bg-slate-100 dark:hover:bg-slate-800'
                  }`}
                >
                  <span className="font-mono font-medium">{t.name}</span>
                  <span className="block text-xs opacity-75">{count(t.row_count)} rows</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <div className="min-w-0 space-y-4">
          <div>
            <h3 className="font-semibold">
              <span className="font-mono">{current.name}</span>: {count(current.row_count)} rows
            </h3>
            <p className="text-sm text-slate-500">
              Keys:{' '}
              {current.candidate_keys.length
                ? current.candidate_keys.map((k) => `(${k.join(', ')})`).join(' ')
                : 'none found'}
            </p>
          </div>
          <TableColumns table={current} keys={profile.data?.keys ?? []} />
          <h4 className="font-semibold">Value overlaps from {current.name}</h4>
          <OverlapList table={current.name} overlaps={profile.data?.overlaps ?? []} />
        </div>
      </div>
    </div>
  )
}
