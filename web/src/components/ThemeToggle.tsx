import { Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'

/** Day mode unless this browser chose night mode before. */
function initialDark(): boolean {
  try {
    return localStorage.getItem('joinpilot-theme') === 'dark'
  } catch {
    return false // storage can be unavailable (private mode)
  }
}

/** Switches between light and dark themes and remembers the choice. */
export function ThemeToggle() {
  const [dark, setDark] = useState(initialDark)
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    try {
      localStorage.setItem('joinpilot-theme', dark ? 'dark' : 'light')
    } catch {
      // ignore
    }
  }, [dark])
  return (
    <button
      type="button"
      onClick={() => setDark((d) => !d)}
      className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
      aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
    >
      {dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
    </button>
  )
}
