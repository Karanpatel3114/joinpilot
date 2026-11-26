import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { StatChip } from './StatChip'

type Props = {
  eyebrow: string
  icon: LucideIcon
  iconClass: string
  title: string
  children: ReactNode
  stat: { value: string; label: string }
  visual: ReactNode
  flip?: boolean
}

/** One feature: label, heading, text and a measured number, beside a small product view. */
export function Feature({ eyebrow, icon: Icon, iconClass, title, children, stat, visual, flip = false }: Props) {
  return (
    <article
      className={`grid items-center gap-10 py-14 md:gap-16 md:py-20 ${flip ? 'md:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]' : 'md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]'}`}
    >
      <div className={flip ? 'md:order-2' : ''}>
        <p className="eyebrow flex items-center gap-3">
          <span className={`flex h-6 w-6 items-center justify-center rounded-md ${iconClass}`}>
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
          </span>
          {eyebrow}
        </p>
        <h3 className="mt-4 text-3xl font-medium tracking-[-0.035em] text-balance sm:text-[40px] sm:leading-[1.08]">{title}</h3>
        <p className="mt-4 max-w-md text-[16px] leading-relaxed text-slate-600 dark:text-slate-300">{children}</p>
        <div className="mt-8">
          <StatChip {...stat} />
        </div>
      </div>
      <div
        className="relative overflow-hidden rounded-[22px] bg-brand-50 p-6 sm:p-10 dark:bg-slate-900"
        style={{
          backgroundImage:
            'repeating-linear-gradient(-38deg, rgb(27 40 17 / 0.07) 0 1px, transparent 1px 7px)',
        }}
      >
        {visual}
      </div>
    </article>
  )
}
