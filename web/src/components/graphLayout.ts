import type { Proposal } from '../types/api'

export const COLUMN_GAP = 300
export const ROW_GAP = 120

export type Point = { x: number; y: number }

export type GraphLayout = {
  /** Top-left corner of each table's node. */
  positions: Map<string, Point>
  /** For an edge that skips columns, the top-left corners of the empty slots it runs through. */
  waypoints: Map<string, Point[]>
}

export const tableOf = (column: string) => column.split('.')[0]

/** Recommended links in a stable order, without the ones that would close a cycle. */
function forwardLinks(proposals: Proposal[], tables: string[]) {
  const links = proposals
    .filter((p) => p.recommended)
    .map((p) => ({ id: p.edge_id, from: tableOf(p.from), to: tableOf(p.to) }))
  const out = new Map(tables.map((t) => [t, links.filter((l) => l.from === t)]))
  const state = new Map<string, 'open' | 'done'>()
  const back = new Set<string>()
  const visit = (table: string) => {
    state.set(table, 'open')
    for (const link of out.get(table) ?? []) {
      const seen = state.get(link.to)
      if (seen === 'open') back.add(link.id)
      else if (!seen) visit(link.to)
    }
    state.set(table, 'done')
  }
  for (const table of tables) if (!state.has(table)) visit(table)
  return links.filter((l) => !back.has(l.id) && l.from !== l.to)
}

/** Lay the graph out left to right: each table one column after its deepest parent, each
 * column ordered by its parents' rows. An edge that skips columns gets an empty slot in every
 * column it crosses, and is drawn through those slots so it never runs across another table. */
export function layout(proposals: Proposal[]): GraphLayout {
  const tables = [...new Set(proposals.flatMap((p) => [tableOf(p.from), tableOf(p.to)]))].sort()
  const links = forwardLinks(proposals, tables)
  const depth = new Map(tables.map((t) => [t, 0]))
  for (let i = 0; i < tables.length; i += 1) {
    for (const { from, to } of links) {
      depth.set(to, Math.max(depth.get(to) ?? 0, (depth.get(from) ?? 0) + 1))
    }
  }
  const columns = new Map<number, string[]>()
  const parents = new Map<string, string[]>()
  const slots = new Map<string, string[]>()
  const place = (id: string, column: number) =>
    columns.set(column, [...(columns.get(column) ?? []), id])
  for (const table of tables) place(table, depth.get(table) ?? 0)
  for (const link of links) {
    let previous = link.from
    const route: string[] = []
    for (let column = (depth.get(link.from) ?? 0) + 1; column < (depth.get(link.to) ?? 0); column += 1) {
      const slot = `slot:${link.id}:${column}`
      place(slot, column)
      parents.set(slot, [previous])
      route.push(slot)
      previous = slot
    }
    parents.set(link.to, [...(parents.get(link.to) ?? []), previous])
    if (route.length) slots.set(link.id, route)
  }
  const at = new Map<string, Point>()
  for (const column of [...columns.keys()].sort((a, b) => a - b)) {
    const centre = (id: string) => {
      const rows = (parents.get(id) ?? []).flatMap((p) => (at.has(p) ? [(at.get(p)?.y ?? 0) / ROW_GAP] : []))
      return rows.length ? rows.reduce((a, b) => a + b, 0) / rows.length : Number.MAX_SAFE_INTEGER
    }
    const ordered = [...(columns.get(column) ?? [])].sort((a, b) => centre(a) - centre(b))
    ordered.forEach((id, row) => at.set(id, { x: column * COLUMN_GAP, y: row * ROW_GAP }))
  }
  return {
    positions: new Map(tables.map((t) => [t, at.get(t) ?? { x: 0, y: 0 }])),
    waypoints: new Map(
      [...slots].map(([id, route]) => [id, route.map((slot) => at.get(slot) ?? { x: 0, y: 0 })]),
    ),
  }
}
