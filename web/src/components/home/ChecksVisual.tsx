import { Check } from 'lucide-react'

const CHECKS = ['Row count kept after joins', 'Orphan keys under 5%', 'Money totals reconcile', 'Primary key is unique']

/** Example of the automated checks that run on every generated view. */
export function ChecksVisual() {
  return (
    <div aria-hidden="true" className="mx-auto max-w-md rounded-xl bg-white p-5 shadow-[0_1px_2px_rgba(11,17,8,0.06)] dark:bg-slate-950">
      <div className="flex items-center justify-between">
        <span className="eyebrow">Example · checks on v_sales</span>
        <span className="font-mono text-[11px] text-slate-500 dark:text-slate-400">0 repairs</span>
      </div>
      <ul className="mt-4 space-y-2.5">
        {CHECKS.map((c) => (
          <li key={c} className="flex items-center gap-3 text-[14px]">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-brand-600 dark:bg-brand-300">
              <Check className="h-3 w-3 text-brand-300 dark:text-brand-600" strokeWidth={3} />
            </span>
            {c}
          </li>
        ))}
      </ul>
      <pre className="mt-5 overflow-hidden rounded-lg bg-slate-50 p-3 font-mono text-[11px] leading-relaxed text-slate-700 dark:bg-slate-900 dark:text-slate-300">
        {`CREATE VIEW v_sales AS\nSELECT i.*, h.KUNNR, h.ERDAT\nFROM VBAP AS i\nJOIN VBAK AS h ON i.VBELN = h.VBELN`}
      </pre>
    </div>
  )
}
