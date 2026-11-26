/** Chart colours, validated with the dataviz palette checker against the card surfaces.
 * One series uses one blue; aging buckets are ordered, so they get one-hue ordinal ramps
 * (light end clears 2:1 on white, dark end on slate-900). */
export const CHART = {
  light: {
    series: '#257de0',
    ordinal: ['#84b9f3', '#519ced', '#257de0', '#1b64be', '#0f4a96'],
    grid: '#e2e8f0',
    axis: '#64748b',
    text: '#0f172a',
    surface: '#ffffff',
  },
  dark: {
    series: '#338ced',
    ordinal: ['#1757ac', '#2370cd', '#338ced', '#6aabf1', '#9dc8f7'],
    grid: '#1e293b',
    axis: '#94a3b8',
    text: '#f1f5f9',
    surface: '#0f172a',
  },
} as const

const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 })
const full = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })

/** Short axis numbers like 12.8M. */
export const axisNumber = (value: number) => compact.format(value)

/** Exact numbers with separators and at most two decimals. */
export function cell(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '(none)'
  return typeof value === 'number' ? full.format(value) : value
}

/** Column names as words: bucket_1-30 becomes "1-30", customer_name "customer name". */
export const label = (column: string) => column.replace(/^bucket_/, '').replaceAll('_', ' ')
