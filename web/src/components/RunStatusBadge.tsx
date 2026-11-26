import type { RunStatus } from '../types/api'

const STYLES: Record<RunStatus, string> = {
  queued: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  profiling: 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300',
  ranking: 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300',
  awaiting_approval: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
  generating: 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300',
  checking: 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300',
  repairing: 'bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-300',
  completed: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
  failed: 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300',
}

/** A run status as a coloured pill with plain words. */
export function RunStatusBadge({ status }: { status: RunStatus }) {
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STYLES[status]}`}>
      {status.replace('_', ' ')}
    </span>
  )
}
