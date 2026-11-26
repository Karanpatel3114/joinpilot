/**
 * Headline numbers shown on the home page. Each one is copied from the
 * evaluation results named below (eval/results/, also quoted in the README),
 * so the page never states a number the evaluation did not produce.
 */
export const EVAL_SOURCE = {
  commit: '1a22e17',
  date: '2026-11-26',
  split: 'held-out test',
  url: 'https://github.com/Karanpatel3114/joinpilot/tree/main/eval/results/2026-11-26-1a22e17-test',
}

export const STATS = {
  // Fan-out recall: joins that would duplicate rows, caught (every baseline scores 0.000)
  fanOut: { value: '1.000', label: 'Fan-out recall · baselines 0.000' },
  kpis: { value: '1,248/1,248', label: 'KPI values correct' },
  attacks: { value: '71/71', label: 'SQL attacks blocked' },
}
