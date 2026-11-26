/** An evidence id (ov_…, uk_…) shown as a small monospace tag, so numbers can be traced. */
export function EvidenceId({ id }: { id: string }) {
  return (
    <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-300">
      {id}
    </code>
  )
}
