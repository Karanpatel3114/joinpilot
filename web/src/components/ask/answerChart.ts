import type { Answer, Metric } from '../../types/api'

/** How to show an answer: one big number, a chart, or just the table. */
export type Shape =
  | { kind: 'number'; label: string; value: number | string }
  | { kind: 'chart'; metric: Metric }
  | { kind: 'table' }

const isNumber = (v: unknown) => typeof v === 'number'

/** Pick the shape from the model's chart hint and what the rows actually hold. */
export function shapeOf(answer: Answer): Shape {
  const { rows, columns } = answer
  if (rows.length === 1 && columns.length === 1) {
    const value = rows[0][columns[0]]
    return { kind: 'number', label: columns[0], value: value === null ? '(none)' : typeof value === 'boolean' ? String(value) : value }
  }
  const x = columns.find((c) => rows.some((r) => !isNumber(r[c]) && r[c] !== null))
  const y = columns.filter((c) => c !== x && rows.every((r) => isNumber(r[c]) || r[c] === null))
  if (!x || !y.length || rows.length > 60 || !['bar', 'line'].includes(answer.chart)) {
    return { kind: 'table' }
  }
  const chart = answer.chart === 'line' ? 'line' : 'bar'
  return {
    kind: 'chart',
    metric: {
      metric_id: 'answer',
      title: answer.question,
      description: answer.evidence?.explanation ?? '',
      view: answer.evidence?.views.join(', ') ?? '',
      sql: answer.sql ?? '',
      chart,
      x,
      // One series keeps the single validated blue; the table shows every column.
      y: y.slice(0, 1),
      requested: true,
      data: rows.map((r) =>
        Object.fromEntries(Object.entries(r).map(([k, v]) => [k, typeof v === 'boolean' ? String(v) : v])),
      ),
      status: 'computed',
      message: null,
    },
  }
}
