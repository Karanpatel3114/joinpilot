import { Link, Outlet } from 'react-router'
import { ThemeToggle } from './ThemeToggle'

/** Page frame: header with the product name and theme switch, then the page. */
export function Layout() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-6 py-3">
          <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <img src="/favicon.svg" alt="" className="h-7 w-7" />
            <span className="text-lg">JoinPilot</span>
          </Link>
          <span className="hidden text-sm text-slate-500 sm:inline dark:text-slate-400">
            From raw ERP tables to a tested data model
          </span>
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
