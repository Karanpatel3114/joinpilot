import { Database } from 'lucide-react'
import { Link } from 'react-router'
import type { Project } from '../types/api'

/** One project in the list, linking to its page. */
export function ProjectCard({ project }: { project: Project }) {
  return (
    <Link
      to={`/projects/${project.id}`}
      className="block rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-brand-500 hover:shadow dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="flex items-center gap-2 font-semibold">
        <Database className="h-4 w-4 text-brand-600 dark:text-brand-300" />
        {project.name}
      </div>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        {project.table_count} {project.table_count === 1 ? 'table' : 'tables'} · created{' '}
        {new Date(project.created_at).toLocaleDateString()}
      </p>
    </Link>
  )
}
