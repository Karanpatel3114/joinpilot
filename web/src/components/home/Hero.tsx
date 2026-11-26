import { CheckCircle2 } from 'lucide-react'
import { Link } from 'react-router'
import { HeroArt } from './HeroArt'

/** Fine ruler ticks down one side of the hero, as a quiet "measured" motif. */
function Ruler({ side }: { side: 'left' | 'right' }) {
  return (
    <div
      aria-hidden="true"
      className={`absolute inset-y-6 hidden w-3 text-slate-950/30 sm:block dark:text-white/20 ${side === 'left' ? 'left-0' : 'right-0 rotate-180'}`}
      style={{
        backgroundImage:
          'repeating-linear-gradient(to bottom, currentColor 0 1px, transparent 1px 20px), repeating-linear-gradient(to bottom, currentColor 0 1px, transparent 1px 100px)',
        backgroundSize: '7px 100%, 12px 100%',
        backgroundRepeat: 'no-repeat',
      }}
    />
  )
}

/** Small monospace "data label" boxes that float beside the illustration. */
function DataLabel({ title, lines, className }: { title: string; lines: string[]; className: string }) {
  return (
    <div
      aria-hidden="true"
      className={`absolute hidden border border-slate-400/70 bg-brand-50/90 px-3 py-2 text-left font-mono text-[10px] leading-relaxed text-slate-700 md:block dark:border-slate-700 dark:bg-slate-900/90 dark:text-slate-300 ${className}`}
    >
      <div className="text-slate-500 dark:text-slate-400">► {title}</div>
      {lines.map((line) => (
        <div key={line}>{line}</div>
      ))}
    </div>
  )
}

/** The home page's opening panel: headline, illustration, one-line pitch and actions.
 * With a shared sample project, the main action opens its dashboard. */
export function Hero({ sampleId }: { sampleId?: string }) {
  return (
    <section className="relative overflow-hidden rounded-[28px] bg-brand-50 px-6 pt-16 pb-14 text-center sm:pt-24 dark:bg-slate-900">
      <Ruler side="left" />
      <Ruler side="right" />
      <h1 className="display mx-auto max-w-4xl text-[44px] sm:text-6xl lg:text-[84px]">
        From raw ERP tables to a tested data model
      </h1>

      <div className="relative mx-auto mt-6 h-64 w-64 sm:h-80 sm:w-80">
        <HeroArt />
        <DataLabel className="top-24 -left-52" title="EXAMPLE · JOIN KEY" lines={['VBAP.VBELN = VBAK.VBELN', 'overlap 100% · N:1']} />
        <DataLabel className="top-44 -left-44" title="EXAMPLE · NORMALIZE" lines={["BSID.KUNNR ltrim('0')", 'then join KNA1']} />
        <div
          aria-hidden="true"
          className="absolute top-16 -right-56 hidden w-60 rounded-lg bg-white p-3 text-left shadow-[0_1px_2px_rgba(11,17,8,0.06)] md:block dark:bg-slate-950"
        >
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-600 dark:bg-brand-300">
            <CheckCircle2 className="h-4 w-4 text-brand-300 dark:text-brand-600" />
          </div>
          <div className="mt-2 flex items-end justify-between gap-2">
            <div className="font-mono text-[10px] leading-snug text-slate-600 dark:text-slate-400">
              <div className="font-sans text-[11px] text-slate-950 dark:text-white">Checks on v_sales</div>
              row count · orphans · totals
            </div>
            <div className="text-xl font-semibold tracking-tight">Passed</div>
          </div>
        </div>
      </div>

      <p className="mx-auto mt-8 max-w-xl text-[17px] leading-relaxed text-slate-600 dark:text-slate-300">
        JoinPilot profiles messy ERP tables, proves how they join, and builds checked SQL views and a KPI
        dashboard, with an AI agent that waits for your approval.
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        {sampleId ? (
          <>
            <Link to={`/projects/${sampleId}?tab=Dashboard`} className="btn-primary">
              Open the sample project
            </Link>
            <a href="#projects" className="btn-secondary">
              Start your own
            </a>
          </>
        ) : (
          <a href="#projects" className="btn-primary">
            Start a project
          </a>
        )}
        <a href="#how" className="btn-secondary">
          How it works
        </a>
      </div>
    </section>
  )
}
