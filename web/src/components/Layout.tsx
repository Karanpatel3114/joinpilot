import { Link, Outlet } from 'react-router'
import { ThemeToggle } from './ThemeToggle'

export const REPO_URL = 'https://github.com/Karanpatel3114/joinpilot'

const NAV = 'rounded-md px-3 py-1.5 font-mono text-[13px] text-slate-700 transition-colors hover:text-slate-950 dark:text-slate-300 dark:hover:text-white'

/** Page frame: wordmark, a few links and the theme switch, then the page. */
export function Layout() {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 bg-white/85 backdrop-blur dark:bg-slate-950/85">
        <div className="mx-auto flex max-w-7xl items-center gap-2 px-4 py-4 sm:px-6">
          <Link to="/" className="mr-auto flex items-center gap-2" aria-label="JoinPilot home">
            <img src="/favicon.svg" alt="" className="h-7 w-7" />
            <span className="text-xl font-bold tracking-[-0.05em]">JoinPilot</span>
          </Link>
          <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
            <a href="/#projects" className={NAV}>
              Projects
            </a>
            <a href="/#how" className={NAV}>
              How it works
            </a>
            <a href={`${REPO_URL}#evaluation`} className={NAV} target="_blank" rel="noreferrer">
              Evaluation
            </a>
          </nav>
          <div className="ml-auto flex items-center gap-2 md:ml-6">
            <a
              href={REPO_URL}
              target="_blank"
              rel="noreferrer"
              className="rounded-md bg-slate-100 px-3 py-1.5 font-mono text-[13px] text-slate-950 transition-colors hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700"
            >
              GitHub
            </a>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 pt-2 pb-20 sm:px-6">
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 dark:border-slate-800">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-6 font-mono text-[12px] text-slate-500 sm:px-6 dark:text-slate-400">
          <span>JoinPilot · synthetic data only · open source</span>
          <a href={REPO_URL} target="_blank" rel="noreferrer" className="hover:text-slate-950 dark:hover:text-white">
            Source on GitHub
          </a>
        </div>
      </footer>
    </div>
  )
}
