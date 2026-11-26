import { useProjects } from '../api/hooks'
import { CreateProjectForm } from '../components/CreateProjectForm'
import { ErrorNote } from '../components/ErrorNote'
import { ProjectCard } from '../components/ProjectCard'

/** Lists projects and creates new ones. */
export function ProjectsPage() {
  const projects = useProjects()
  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Projects</h1>
        <p className="mt-1 text-slate-600 dark:text-slate-400">
          Each project holds your tables, their profile and the runs that turn them into a model.
        </p>
      </div>
      <CreateProjectForm />
      <ErrorNote error={projects.error} />
      {projects.isLoading && <p className="text-sm text-slate-500">Loading projects…</p>}
      {projects.data?.length === 0 && (
        <p className="text-sm text-slate-500">No projects yet. Create one to get started.</p>
      )}
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {projects.data?.map((project) => (
          <li key={project.id}>
            <ProjectCard project={project} />
          </li>
        ))}
      </ul>
    </section>
  )
}
