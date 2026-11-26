import { Check, Circle, Loader2, X } from 'lucide-react'
import type { Run } from '../types/api'

const STEPS = [
  { key: 'profile', label: 'Profile tables', active: ['queued', 'profiling'] },
  { key: 'parse_requirement', label: 'Understand the requirement', active: ['ranking'] },
  { key: 'rank_joins', label: 'Rank and explain joins', active: ['ranking'] },
  { key: 'await_approval', label: 'Your approval', active: ['awaiting_approval'] },
  { key: 'generate_views', label: 'Generate views', active: ['generating'] },
  { key: 'check_views', label: 'Run checks (and repair)', active: ['checking', 'repairing'] },
] as const

/** The run's steps with what is done, what is running and how long each took. */
export function RunTimeline({ run }: { run: Run }) {
  return (
    <ol aria-label="Run steps" className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
      {STEPS.map((step) => {
        const ms = run.timings_ms[step.key]
        const running = (step.active as readonly string[]).includes(run.status)
        const done = ms !== undefined && !running
        const failed = run.status === 'failed' && running
        return (
          <li
            key={step.key}
            className="flex items-start gap-2 rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-800"
          >
            {failed ? (
              <X className="h-4 w-4 text-rose-600" />
            ) : done ? (
              <Check className="h-4 w-4 text-emerald-600" />
            ) : running ? (
              <Loader2 className="h-4 w-4 animate-spin text-brand-600" />
            ) : (
              <Circle className="h-4 w-4 text-slate-300" />
            )}
            <span>
              {step.label}
              {done && <span className="block text-xs text-slate-500">{Math.round(ms)} ms</span>}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
