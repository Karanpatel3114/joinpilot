import { Plus } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router'
import { useCreateProject } from '../api/hooks'
import { ErrorNote } from './ErrorNote'

/** Creates a project and opens it. */
export function CreateProjectForm() {
  const [name, setName] = useState('')
  const create = useCreateProject()
  const navigate = useNavigate()

  function submit(event: FormEvent) {
    event.preventDefault()
    create.mutate(name, { onSuccess: (project) => navigate(`/projects/${project.id}`) })
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row sm:items-end">
      <label className="flex flex-1 flex-col gap-1 text-sm font-medium">
        New project name
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Demo ERP"
          maxLength={100}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal dark:border-slate-700 dark:bg-slate-900"
        />
      </label>
      <button
        type="submit"
        disabled={!name.trim() || create.isPending}
        className="inline-flex items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700 disabled:opacity-50"
      >
        <Plus className="h-4 w-4" />
        Create project
      </button>
      <ErrorNote error={create.error} />
    </form>
  )
}
