import { ArrowLeft } from 'lucide-react'
import { type KeyboardEvent, Suspense, lazy, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { useProjects } from '../api/hooks'
import { ProfileExplorer } from '../components/ProfileExplorer'
import { RunsPanel } from '../components/RunsPanel'
import { UploadPanel } from '../components/UploadPanel'

const TABS = ['Profile', 'Runs', 'Dashboard', 'Ask'] as const

// Recharts is large, so the dashboard and the ask panel load when their tab first opens.
const DashboardPanel = lazy(async () => ({
  default: (await import('../components/dashboard/DashboardPanel')).DashboardPanel,
}))
const AskPanel = lazy(async () => ({
  default: (await import('../components/ask/AskPanel')).AskPanel,
}))
type Tab = (typeof TABS)[number]

/** One project: add tables, explore their profile, and run the agent. */
export function ProjectPage() {
  const { projectId = '' } = useParams()
  const project = useProjects().data?.find((p) => p.id === projectId)
  const [params] = useSearchParams()
  const [tab, setTab] = useState<Tab>(() => TABS.find((t) => t === params.get('tab')) ?? 'Profile')
  const hasTables = (project?.table_count ?? 0) > 0

  /** Arrow keys, Home and End move between tabs, as in the ARIA tabs pattern. */
  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    const index = TABS.indexOf(tab)
    const next = { ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: TABS.length - 1 }[event.key]
    if (next === undefined) return
    event.preventDefault()
    const name = TABS[(next + TABS.length) % TABS.length]
    setTab(name)
    document.getElementById(`tab-${name}`)?.focus()
  }
  return (
    <section className="space-y-6">
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-slate-500 dark:text-slate-400 hover:text-brand-600 dark:hover:text-brand-300">
        <ArrowLeft className="h-4 w-4" /> All projects
      </Link>
      <h1 className="text-2xl font-bold tracking-tight">{project?.name ?? 'Project'}</h1>
      <UploadPanel projectId={projectId} />
      {hasTables && (
        <>
          <div role="tablist" aria-label="Project views" onKeyDown={onKey} className="flex gap-2 border-b border-slate-200 dark:border-slate-800">
            {TABS.map((name) => (
              <button
                key={name}
                id={`tab-${name}`}
                role="tab"
                type="button"
                aria-selected={tab === name}
                aria-controls={`panel-${name}`}
                tabIndex={tab === name ? 0 : -1}
                onClick={() => setTab(name)}
                className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
                  tab === name ? 'border-brand-600 text-brand-600 dark:text-brand-300' : 'border-transparent text-slate-500 dark:text-slate-400'
                }`}
              >
                {name}
              </button>
            ))}
          </div>
          <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
            {tab === 'Profile' && <ProfileExplorer projectId={projectId} />}
            {tab === 'Runs' && <RunsPanel projectId={projectId} />}
            {tab === 'Dashboard' && (
              <Suspense fallback={<p className="text-sm text-slate-500 dark:text-slate-400">Loading dashboard…</p>}>
                <DashboardPanel projectId={projectId} />
              </Suspense>
            )}
            {tab === 'Ask' && (
              <Suspense fallback={<p className="text-sm text-slate-500 dark:text-slate-400">Loading…</p>}>
                <AskPanel projectId={projectId} />
              </Suspense>
            )}
          </div>
        </>
      )}
    </section>
  )
}
