import { ArrowLeft } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

type Props = {
  back: { to: string; label: string }
  eyebrow: string
  title: string
  aside?: ReactNode
  children?: ReactNode
}

/** The sage panel that opens a project or run page: back link, label, title and details. */
export function PageHeader({ back, eyebrow, title, aside, children }: Props) {
  return (
    <header
      className="rounded-[28px] bg-brand-50 px-6 py-8 sm:px-10 sm:py-10 dark:bg-slate-900"
      style={{ backgroundImage: 'repeating-linear-gradient(-38deg, rgb(27 40 17 / 0.05) 0 1px, transparent 1px 7px)' }}
    >
      <Link
        to={back.to}
        className="inline-flex items-center gap-1.5 font-mono text-[12px] text-slate-600 hover:text-slate-950 dark:text-slate-400 dark:hover:text-white"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> {back.label}
      </Link>
      <div className="mt-6 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="eyebrow">{eyebrow}</p>
          <h1 className="display mt-3 text-4xl break-words sm:text-[56px]">{title}</h1>
        </div>
        {aside}
      </div>
      {children && <div className="mt-4">{children}</div>}
    </header>
  )
}
