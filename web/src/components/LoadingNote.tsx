import { useEffect, useState } from 'react'

/** After this long, a load is probably the free API server waking up. */
export const SLOW_MS = 4000

/** A loading message that explains the free server's cold start when a load is slow. */
export function LoadingNote({ label }: { label: string }) {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), SLOW_MS)
    return () => clearTimeout(timer)
  }, [])
  return (
    <p role="status" className="text-sm text-slate-500 dark:text-slate-400">
      {label}
      {slow && ' The free demo server sleeps when idle and can take about a minute to wake up.'}
    </p>
  )
}
