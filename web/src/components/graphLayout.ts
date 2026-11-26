import type { Proposal } from '../types/api'

const COLUMN_GAP = 300
const ROW_GAP = 120

export const tableOf = (column: string) => column.split('.')[0]

/** Place tables in columns by how deep they sit in the recommended join graph, then order
 * each column by the average row of its parents. An edge that skips columns reserves an
 * empty slot in every column it crosses, so it never runs through another table. */
export function layout(proposals: Proposal[]): Map<string, { x: number; y: number }> {
  const tables = [...new Set(proposals.flatMap((p) => [tableOf(p.from), tableOf(p.to)]))].sort()
  const links = proposals
    .filter((p) => p.recommended)
    .map((p) => [tableOf(p.from), tableOf(p.to)] as const)
  const depth = new Map(tables.map((t) => [t, 0]))
  for (let i = 0; i < tables.length; i += 1) {
    for (const [from, to] of links) {
      depth.set(to, Math.min(Math.max(depth.get(to) ?? 0, (depth.get(from) ?? 0) + 1), tables.length))
    }
  }
  const columns = new Map<number, string[]>()
  const parents = new Map<string, string[]>()
  const place = (id: string, column: number) => columns.set(column, [...(columns.get(column) ?? []), id])
  for (const table of tables) place(table, depth.get(table) ?? 0)
  links.forEach(([from, to], index) => {
    let previous = from
    for (let column = (depth.get(from) ?? 0) + 1; column < (depth.get(to) ?? 0); column += 1) {
      const slot = `\u0000${index}:${column}`
      place(slot, column)
      parents.set(slot, [previous])
      previous = slot
    }
    parents.set(to, [...(parents.get(to) ?? []), previous])
  })
  const row = new Map<string, number>()
  for (const column of [...columns.keys()].sort((a, b) => a - b)) {
    const centre = (id: string) => {
      const known = (parents.get(id) ?? []).filter((p) => row.has(p)).map((p) => row.get(p) ?? 0)
      return known.length ? known.reduce((a, b) => a + b, 0) / known.length : Infinity
    }
    const ordered = [...(columns.get(column) ?? [])].sort((a, b) => centre(a) - centre(b))
    ordered.forEach((id, index) => row.set(id, index))
  }
  return new Map(
    tables.map((t) => [t, { x: (depth.get(t) ?? 0) * COLUMN_GAP, y: (row.get(t) ?? 0) * ROW_GAP }]),
  )
}
