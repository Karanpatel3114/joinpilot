import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { useProjects } from '../api/hooks'
import { ProfileExplorer } from '../components/ProfileExplorer'
import { RunsPanel } from '../components/RunsPanel'
import { UploadPanel } from '../components/UploadPanel'

const TABS = ['Profile', 'Runs'] as const
type Tab = (typeof TABS)[number]

/** One project: add tables, explore their profile, and run the agent. */
export function ProjectPage() {
  const { projectId = '' } = useParams()
  const project = useProjects().data?.find((p) => p.id === projectId)
  const [tab, setTab] = useState<Tab>('Profile')
  const hasTables = (project?.table_count ?? 0) > 0
  return (
    <section className="space-y-6">
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-brand-600">
        <ArrowLeft className="h-4 w-4" /> All projects
      </Link>
      <h1 className="text-2xl font-bold tracking-tight">{project?.name ?? 'Project'}</h1>
      <UploadPanel projectId={projectId} />
      {hasTables && (
        <>
          <div role="tablist" aria-label="Project views" className="flex gap-2 border-b border-slate-200 dark:border-slate-800">
            {TABS.map((name) => (
              <button
                key={name}
                role="tab"
                type="button"
                aria-selected={tab === name}
                onClick={() => setTab(name)}
                className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
                  tab === name ? 'border-brand-600 text-brand-600' : 'border-transparent text-slate-500'
                }`}
              >
                {name}
              </button>
            ))}
          </div>
          {tab === 'Profile' && <ProfileExplorer projectId={projectId} />}
          {tab === 'Runs' && <RunsPanel projectId={projectId} />}
        </>
      )}
    </section>
  )
}
