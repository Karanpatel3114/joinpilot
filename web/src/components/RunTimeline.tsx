import { Check, Circle, Loader2, X } from 'lucide-react'
import type { Run } from '../types/api'

const STEPS = [
  { key: 'profile', label: 'Profile tables', active: ['queued', 'profiling'] },
  { key: 'parse_requirement', label: 'Understand the requirement', active: ['ranking'] },
  { key: 'rank_joins', label: 'Rank and explain joins', active: ['ranking'] },
  { key: 'await_approval', label: 'Your approval', active: ['awaiting_approval'] },
  { key: 'generate_views', label: 'Generate views', active: ['generating'] },
  { key: 'check_views', label: 'Run checks (and repair)', active: ['checking', 'repairing'] },
  { key: 'build_dashboard', label: 'Build the dashboard', active: [] },
] as const

/** The run's steps with what is done, what is running and how long each took. */
export function RunTimeline({ run }: { run: Run }) {
  const failedAt =
    run.status === 'failed' ? STEPS.findIndex((s) => run.timings_ms[s.key] === undefined) : -1
  return (
    <ol aria-label="Run steps" className="grid gap-2 sm:grid-cols-3 lg:grid-cols-7">
      {STEPS.map((step, index) => {
        const ms = run.timings_ms[step.key]
        // Checks rerun after a repair, so that step keeps spinning while it has a timing.
        const rerun = step.key === 'check_views'
        const running =
          (step.active as readonly string[]).includes(run.status) && (ms === undefined || rerun)
        const done = ms !== undefined && !running
        const failed = index === failedAt
        return (
          <li
            key={step.key}
            aria-label={`${step.label}: ${failed ? 'failed' : done ? 'done' : running ? 'running' : 'not started'}`}
            className="flex items-start gap-2 rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-800"
          >
            {failed ? (
              <X className="h-4 w-4 text-rose-600" />
            ) : done ? (
              <Check className="h-4 w-4 text-emerald-600" />
            ) : running ? (
              <Loader2 className="h-4 w-4 animate-spin text-brand-600 dark:text-brand-300" />
            ) : (
              <Circle className="h-4 w-4 text-slate-300" />
            )}
            <span>
              {step.label}
              {done && <span className="block text-xs text-slate-500 dark:text-slate-400">{Math.round(ms)} ms</span>}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
