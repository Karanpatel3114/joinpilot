import { ShieldCheck } from 'lucide-react'

/** Example of a plain-English question answered with guarded, read-only SQL. */
export function AskVisual() {
  return (
    <div aria-hidden="true" className="mx-auto max-w-md space-y-3">
      <div className="ml-auto w-fit max-w-[85%] rounded-xl rounded-br-sm bg-brand-600 px-4 py-2.5 text-[14px] text-white dark:bg-brand-300 dark:text-brand-700">
        Which customers have the most overdue receivables?
      </div>
      <div className="rounded-xl bg-white p-5 shadow-[0_1px_2px_rgba(11,17,8,0.06)] dark:bg-slate-950">
        <div className="flex items-center justify-between">
          <span className="eyebrow">Example · answer</span>
          <span className="flex items-center gap-1 font-mono text-[11px] text-slate-600 dark:text-slate-300">
            <ShieldCheck className="h-3.5 w-3.5" /> guard passed
          </span>
        </div>
        <pre className="mt-3 overflow-hidden rounded-lg bg-slate-50 p-3 font-mono text-[11px] leading-relaxed text-slate-700 dark:bg-slate-900 dark:text-slate-300">
          {`SELECT customer_name,\n       SUM(amount) AS overdue\nFROM v_open_items\nWHERE days_overdue > 0\nGROUP BY 1 ORDER BY 2 DESC\nLIMIT 10`}
        </pre>
        <p className="mt-3 font-mono text-[11px] text-slate-500 dark:text-slate-400">read-only · 10 rows · shows its SQL</p>
      </div>
    </div>
  )
}
