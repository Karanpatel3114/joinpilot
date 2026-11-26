import { Link } from 'react-router'
import { useDashboard } from '../../api/hooks'
import { ErrorNote } from '../ErrorNote'
import { MetricCard } from './MetricCard'

/** The KPI dashboard of the project's newest completed run. */
export function DashboardPanel({ projectId }: { projectId: string }) {
  const dashboard = useDashboard(projectId)
  if (dashboard.error) return <ErrorNote error={dashboard.error} />
  if (!dashboard.data) return <p className="text-sm text-slate-500 dark:text-slate-400">Loading dashboard…</p>
  const { run_id: runId, metrics } = dashboard.data
  const source = runId && (
    <p className="text-sm text-slate-600 dark:text-slate-400">
      From the latest completed run,{' '}
      <Link to={`/runs/${runId}`} className="font-mono text-brand-600 hover:underline dark:text-brand-300">
        {runId.slice(0, 8)}
      </Link>
      . Numbers come only from views that passed their row count, fan-out and reconciliation checks.
    </p>
  )
  if (runId && !metrics.length) {
    return (
      <div className="space-y-3">
        {source}
        <p className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-600 dark:border-slate-700 dark:text-slate-400">
          That run produced no KPIs: no joins were approved, or the model lacks the columns the
          metrics need.
        </p>
      </div>
    )
  }
  if (!metrics.length) {
    return (
      <p className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-600 dark:border-slate-700 dark:text-slate-400">
        No dashboard yet. Start a run, approve its joins, and the KPIs your model supports appear here.
      </p>
    )
  }
  return (
    <div className="space-y-3">
      {source}
      <section aria-label="Dashboard" className="grid gap-4 xl:grid-cols-2">
        {metrics.map((metric) => (
          <MetricCard key={metric.metric_id} metric={metric} />
        ))}
      </section>
    </div>
  )
}
