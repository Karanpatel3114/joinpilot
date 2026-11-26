import type { RunStatus } from '../types/api'

const STYLES: Record<RunStatus, string> = {
  queued: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  profiling: 'bg-brand-100 text-slate-800 dark:bg-slate-800 dark:text-brand-300',
  ranking: 'bg-brand-100 text-slate-800 dark:bg-slate-800 dark:text-brand-300',
  awaiting_approval: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
  generating: 'bg-brand-100 text-slate-800 dark:bg-slate-800 dark:text-brand-300',
  checking: 'bg-brand-100 text-slate-800 dark:bg-slate-800 dark:text-brand-300',
  repairing: 'bg-orange-100 text-orange-900 dark:bg-orange-950 dark:text-orange-300',
  completed: 'bg-brand-600 text-brand-300 dark:bg-brand-300 dark:text-brand-700',
  failed: 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300',
}

/** A run status as a coloured pill with plain words. */
export function RunStatusBadge({ status }: { status: RunStatus }) {
  return (
    <span className={`rounded-md px-2.5 py-1 font-mono text-[11px] font-medium ${STYLES[status]}`}>
      {status.replace('_', ' ')}
    </span>
  )
}
