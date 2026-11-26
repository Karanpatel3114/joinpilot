import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Metric } from '../../types/api'
import { useDarkMode } from '../useDarkMode'
import { CHART, axisNumber, cell, label } from './chartTheme'

/** A metric's rows as a bar or line chart: one blue series, or an ordinal ramp when the
 * values are ordered buckets. Long category names (customers) get horizontal bars. */
export function MetricChart({ metric }: { metric: Metric }) {
  const theme = CHART[useDarkMode() ? 'dark' : 'light']
  const rows = metric.data.map((row) => ({ ...row, [metric.x]: cell(row[metric.x]) }))
  const stacked = metric.y.length > 1
  const horizontal = metric.x.includes('name')
  const tooltip = (
    <Tooltip
      cursor={{ fill: theme.grid, opacity: 0.5 }}
      formatter={(value, name) => [cell(value as number), label(String(name))]}
      contentStyle={{ background: theme.surface, borderColor: theme.grid, color: theme.text, borderRadius: 8 }}
      labelStyle={{ color: theme.text, fontWeight: 600 }}
    />
  )
  const axis = { stroke: theme.axis, fontSize: 12, tickLine: false }

  if (metric.chart === 'line') {
    return (
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={theme.grid} />
          <XAxis dataKey={metric.x} {...axis} />
          <YAxis {...axis} axisLine={false} tickFormatter={axisNumber} width={48} />
          {tooltip}
          <Line
            dataKey={metric.y[0]}
            name={metric.y[0]}
            stroke={theme.series}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 5, stroke: theme.surface, strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    )
  }

  const colour = (i: number) => (stacked ? theme.ordinal[i % theme.ordinal.length] : theme.series)
  const radius = (i: number): [number, number, number, number] => {
    if (i !== metric.y.length - 1) return [0, 0, 0, 0]
    return horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]
  }
  return (
    <ResponsiveContainer width="100%" height={horizontal ? Math.max(220, rows.length * 30 + 60) : 260}>
      <BarChart
        data={rows}
        layout={horizontal ? 'vertical' : 'horizontal'}
        margin={{ top: 8, right: 16, bottom: 0, left: 0 }}
        barCategoryGap="20%"
      >
        <CartesianGrid horizontal={!horizontal} vertical={horizontal} stroke={theme.grid} />
        {horizontal ? (
          <>
            <XAxis type="number" {...axis} tickFormatter={axisNumber} />
            <YAxis type="category" dataKey={metric.x} {...axis} width={150} interval={0} />
          </>
        ) : (
          <>
            <XAxis dataKey={metric.x} {...axis} interval={0} />
            <YAxis {...axis} axisLine={false} tickFormatter={axisNumber} width={48} />
          </>
        )}
        {tooltip}
        {stacked && (
          <Legend
            itemSorter={null}
            iconType="square"
            iconSize={10}
            wrapperStyle={{ fontSize: 12 }}
            formatter={(value) => <span style={{ color: theme.text }}>{label(String(value))}</span>}
          />
        )}
        {metric.y.map((key, i) => (
          <Bar
            key={key}
            dataKey={key}
            name={key}
            stackId={stacked ? 'total' : undefined}
            fill={colour(i)}
            stroke={stacked ? theme.surface : undefined}
            strokeWidth={stacked ? 2 : 0}
            radius={radius(i)}
            maxBarSize={48}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}
