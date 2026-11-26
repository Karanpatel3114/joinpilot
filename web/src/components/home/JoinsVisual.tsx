const ROWS = [
  ['Overlap', '100.0%'],
  ['Key uniqueness', '100.0%'],
  ['Cardinality', 'N:1'],
  ['Fan-out risk', 'none'],
]

/** Example of a proposed join with its evidence, as the console shows it. */
export function JoinsVisual() {
  return (
    <div aria-hidden="true" className="mx-auto max-w-md rounded-xl bg-white p-5 shadow-[0_1px_2px_rgba(11,17,8,0.06)] dark:bg-slate-950">
      <div className="flex items-center justify-between">
        <span className="eyebrow">Example · proposed join</span>
        <span className="rounded-md bg-brand-50 px-2 py-0.5 font-mono text-[11px] text-slate-700 dark:bg-slate-800 dark:text-brand-300">recommended</span>
      </div>
      <p className="mt-3 font-mono text-[13px]">
        VBAP.VBELN <span className="text-slate-400">→</span> VBAK.VBELN
      </p>
      <dl className="mt-4 divide-y divide-slate-100 font-mono text-[12px] dark:divide-slate-800">
        {ROWS.map(([k, v]) => (
          <div key={k} className="flex justify-between py-2">
            <dt className="text-slate-500 dark:text-slate-400">{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-4 flex gap-2">
        <span className="btn-primary px-3 py-1.5">Approve</span>
        <span className="btn-secondary px-3 py-1.5">Reject</span>
      </div>
    </div>
  )
}
