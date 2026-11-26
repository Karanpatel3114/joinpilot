import { useDashboard } from '../../api/hooks'
import { ErrorNote } from '../ErrorNote'
import { MetricCard } from './MetricCard'

/** The KPI dashboard of the project's newest completed run. */
export function DashboardPanel({ projectId }: { projectId: string }) {
  const dashboard = useDashboard(projectId)
  if (dashboard.error) return <ErrorNote error={dashboard.error} />
  if (!dashboard.data) return <p className="text-sm text-slate-500 dark:text-slate-400">Loading dashboard…</p>
  if (!dashboard.data.metrics.length) {
    return (
      <p className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-600 dark:border-slate-700 dark:text-slate-400">
        No dashboard yet. Start a run, approve its joins, and the KPIs your model supports appear here.
      </p>
    )
  }
  return (
    <section aria-label="Dashboard" className="grid gap-4 xl:grid-cols-2">
      {dashboard.data.metrics.map((metric) => (
        <MetricCard key={metric.metric_id} metric={metric} />
      ))}
    </section>
  )
}
