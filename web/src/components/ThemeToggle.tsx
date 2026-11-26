import { Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'

function initialDark(): boolean {
  try {
    const saved = localStorage.getItem('joinpilot-theme')
    if (saved) return saved === 'dark'
  } catch {
    // storage can be unavailable (private mode); fall back to the system setting
  }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
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
