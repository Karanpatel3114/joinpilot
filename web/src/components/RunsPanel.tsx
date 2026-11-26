import { Play } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { useRuns, useStartRun } from '../api/hooks'
import { ErrorNote } from './ErrorNote'
import { RunStatusBadge } from './RunStatusBadge'

const EXAMPLES = [
  'Open receivables by customer and aging bucket, plus 2026 revenue by product group.',
  'Monthly order counts and the top customers by revenue.',
]

/** Start a run from a plain-English requirement, and list earlier runs. */
export function RunsPanel({ projectId }: { projectId: string }) {
  const [requirement, setRequirement] = useState(EXAMPLES[0])
  const start = useStartRun(projectId)
  const runs = useRuns(projectId)
  const navigate = useNavigate()

  function submit(event: FormEvent) {
    event.preventDefault()
    start.mutate(requirement, { onSuccess: (run) => navigate(`/runs/${run.run_id}`) })
  }

  return (
    <div className="space-y-6">
      <form onSubmit={submit} className="space-y-2">
        <label className="flex flex-col gap-1 text-sm font-medium">
          What should the data model answer?
          <textarea
            value={requirement}
            onChange={(e) => setRequirement(e.target.value)}
            rows={3}
            maxLength={2000}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal dark:border-slate-700 dark:bg-slate-900"
          />
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="submit"
            disabled={requirement.trim().length < 3 || start.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            <Play className="h-4 w-4" /> Start run
          </button>
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => setRequirement(example)}
              className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {example.split(',')[0]}
            </button>
          ))}
        </div>
        <ErrorNote error={start.error} />
      </form>
      <ul aria-label="Runs" className="space-y-2">
        {runs.data?.map((run) => (
          <li key={run.run_id}>
            <Link
              to={`/runs/${run.run_id}`}
              className="flex items-center justify-between gap-4 rounded-lg border border-slate-200 px-3 py-2 text-sm hover:border-brand-500 dark:border-slate-800"
            >
              <span className="truncate">{run.requirement}</span>
              <RunStatusBadge status={run.status} />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
