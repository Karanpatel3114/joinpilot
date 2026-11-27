/** Chart colours, validated with the dataviz palette checker against the card surfaces.
 * One series uses one green; aging buckets are ordered, so they get one-hue ordinal ramps
 * (light end clears 2:1 on white, dark end on the dark card colour). */
export const CHART = {
  light: {
    series: '#4a882c',
    ordinal: ['#8cc260', '#66a43f', '#4a882c', '#33701d', '#1d4c0f'],
    grid: '#e5e7e1',
    axis: '#6b7064',
    text: '#0b1108',
    surface: '#ffffff',
  },
  dark: {
    series: '#62a83e',
    ordinal: ['#2f6a1c', '#43892a', '#62a83e', '#8fcb63', '#bfe988'],
    grid: '#263020',
    axis: '#a3a89b',
    text: '#eff1ec',
    surface: '#141c0f',
  },
} as const

const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 })
const full = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })

/** Short axis numbers like 12.8M. */
export const axisNumber = (value: number) => compact.format(value)

/** Exact numbers with separators and at most two decimals. */
export function cell(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined) return '(none)'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return typeof value === 'number' ? full.format(value) : value
}

/** Column names as words: bucket_1-30 becomes "1-30", customer_name "customer name". */
export const label = (column: string) => column.replace(/^bucket_/, '').replaceAll('_', ' ')
