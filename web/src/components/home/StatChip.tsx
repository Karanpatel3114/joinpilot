/** A headline number with a small monospace caption, on a sage chip. */
export function StatChip({ value, label }: { value: string; label: string }) {
  return (
    <p className="inline-flex items-baseline gap-3 rounded-lg bg-brand-50 px-3 py-2 dark:bg-slate-900">
      <span className="text-2xl font-medium tracking-[-0.03em]">{value}</span>
      <span className="font-mono text-[10px] tracking-[0.12em] text-slate-700 uppercase dark:text-slate-300">{label}</span>
    </p>
  )
}
