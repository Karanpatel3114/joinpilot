import { Database } from 'lucide-react'
import { Link } from 'react-router'
import type { Project } from '../types/api'

/** One project in the list, linking to its page. */
export function ProjectCard({ project }: { project: Project }) {
  return (
    <Link
      to={`/projects/${project.id}`}
      className="card block p-5 transition-colors hover:border-slate-950 dark:hover:border-brand-300"
    >
      <div className="flex items-center gap-2 text-lg font-semibold tracking-tight">
        <Database className="h-4 w-4 text-brand-600 dark:text-brand-300" />
        {project.name}
      </div>
      <p className="mt-2 font-mono text-[12px] text-slate-500 dark:text-slate-400">
        {project.table_count} {project.table_count === 1 ? 'table' : 'tables'} · created{' '}
        {new Date(project.created_at).toLocaleDateString()}
      </p>
    </Link>
  )
}
