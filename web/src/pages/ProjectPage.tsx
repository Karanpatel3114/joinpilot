import { type KeyboardEvent, Suspense, lazy, useState } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { useProjects } from '../api/hooks'
import { ErrorNote } from '../components/ErrorNote'
import { PageHeader } from '../components/PageHeader'
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
  const projects = useProjects()
  const project = projects.data?.find((p) => p.id === projectId)
  const [params] = useSearchParams()
  const [tab, setTab] = useState<Tab>(() => TABS.find((t) => t === params.get('tab')) ?? 'Profile')
  // Until the project list arrives, assume read-only so upload buttons never flash on the sample.
  const readOnly = project?.read_only ?? !projects.data
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
  if (!project) {
    return (
      <section className="space-y-8">
        <PageHeader back={{ to: '/#projects', label: 'All projects' }} eyebrow="Project" title="Project" />
        {projects.error ? (
          <ErrorNote error={projects.error} />
        ) : projects.data ? (
          <p role="alert" className="max-w-2xl text-[15px] text-slate-600 dark:text-slate-300">
            This project was not found. Projects belong to the browser that created them, and the free demo
            server clears its data when it restarts. Create a new project from the home page.
          </p>
        ) : (
          <p className="text-sm text-slate-500 dark:text-slate-400">Loading project…</p>
        )}
      </section>
    )
  }
  return (
    <section className="space-y-8">
      <PageHeader back={{ to: '/#projects', label: 'All projects' }} eyebrow="Project" title={project.name}>
        <p className="font-mono text-[12px] text-slate-600 dark:text-slate-400">
          {project.table_count} {project.table_count === 1 ? 'table' : 'tables'} · created{' '}
          {new Date(project.created_at).toLocaleDateString()}
        </p>
        {readOnly && (
          <p className="mt-3 max-w-2xl text-[15px] text-slate-600 dark:text-slate-300">
            A shared sample, built when the demo started: its joins were approved automatically. Look around
            freely; to upload, run and approve yourself, create your own project from the home page.
          </p>
        )}
      </PageHeader>
      {!readOnly && <UploadPanel projectId={projectId} />}
      {hasTables && (
        <>
          <div role="tablist" aria-label="Project views" onKeyDown={onKey} className="inline-flex flex-wrap gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-900">
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
                className={`rounded-md px-4 py-1.5 font-mono text-[13px] transition-colors ${
                  tab === name
                    ? 'bg-white text-slate-950 shadow-[0_1px_2px_rgba(11,17,8,0.08)] dark:bg-slate-800 dark:text-white'
                    : 'text-slate-600 hover:text-slate-950 dark:text-slate-400 dark:hover:text-white'
                }`}
              >
                {name}
              </button>
            ))}
          </div>
          <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="pt-2">
            {tab === 'Profile' && <ProfileExplorer projectId={projectId} />}
            {tab === 'Runs' && <RunsPanel projectId={projectId} readOnly={readOnly} />}
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
