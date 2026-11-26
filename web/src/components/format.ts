/** A ratio shown as a percentage with one decimal, like the explanations use. */
export function pct(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}%`
}

/** Thousands separators for counts. */
export function count(value: number): string {
  return value.toLocaleString('en-US')
}
