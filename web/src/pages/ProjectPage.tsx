import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { useProjects } from '../api/hooks'
import { UploadPanel } from '../components/UploadPanel'

/** One project: its tables, profile and runs. */
export function ProjectPage() {
  const { projectId = '' } = useParams()
  const project = useProjects().data?.find((p) => p.id === projectId)
  return (
    <section className="space-y-6">
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-brand-600">
        <ArrowLeft className="h-4 w-4" /> All projects
      </Link>
      <h1 className="text-2xl font-bold tracking-tight">{project?.name ?? 'Project'}</h1>
      <UploadPanel projectId={projectId} />
    </section>
  )
}
