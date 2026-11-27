import { AlertTriangle } from 'lucide-react'
import { errorMessage } from '../api/errorMessage'

/** A visible, plain-language error message. */
export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null
  const message = errorMessage(error)
  return (
    <p
      role="alert"
      className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-200"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      {message}
    </p>
  )
}
