/** A ratio shown as a percentage with one decimal, like the explanations use. */
export function pct(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}%`
}

/** Thousands separators for counts. */
export function count(value: number): string {
  return value.toLocaleString('en-US')
}

/** A check value: numbers with separators and at most two decimals, text as is. */
export function value(v: number | string | null): string {
  if (v === null) return ''
  return typeof v === 'number' ? v.toLocaleString('en-US', { maximumFractionDigits: 2 }) : v
}
