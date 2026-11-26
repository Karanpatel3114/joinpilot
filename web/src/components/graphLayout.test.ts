import { describe, expect, it } from 'vitest'
import proposals from '../../../shared/fixtures/proposals.json'
import type { Proposal } from '../types/api'
import { COLUMN_GAP, layout, tableOf } from './graphLayout'

const fixture = proposals as Proposal[]

/** Minimal recommended proposals from "A>B" pairs. */
function edges(...pairs: string[]): Proposal[] {
  return pairs.map((pair, i) => {
    const [from, to] = pair.split('>')
    return { ...fixture[0], edge_id: `e${i + 1}`, from: `${from}.k`, to: `${to}.k`, recommended: true }
  })
}

/** Every column an edge crosses holds a reserved slot, and no table sits in any slot. */
function expectClearRoutes(list: Proposal[]) {
  const { positions, waypoints } = layout(list)
  const taken = new Set([...positions.values()].map((p) => `${p.x},${p.y}`))
  for (const p of list) {
    const from = positions.get(tableOf(p.from))
    const to = positions.get(tableOf(p.to))
    if (!from || !to || to.x <= from.x) continue
    const route = waypoints.get(p.edge_id) ?? []
    expect(route.map((w) => w.x)).toEqual(
      Array.from({ length: (to.x - from.x) / COLUMN_GAP - 1 }, (_, i) => from.x + (i + 1) * COLUMN_GAP),
    )
    for (const w of route) expect(taken.has(`${w.x},${w.y}`), `${p.edge_id} crosses a table`).toBe(false)
  }
}

describe('join graph layout', () => {
  it('puts each table one column after its deepest parent', () => {
    const at = layout(fixture).positions
    expect(at.get('VBAP')?.x).toBe(0)
    expect(at.get('VBAK')?.x).toBe(COLUMN_GAP)
    expect(at.get('KNA1')?.x).toBe(2 * COLUMN_GAP)
  })

  it('routes the fixture edge BSID to KNA1 through an empty slot', () => {
    expect(layout(fixture).waypoints.get('e5')).toHaveLength(1)
    expectClearRoutes(fixture)
  })

  it('keeps long edges clear when several tables share a column', () => {
    expectClearRoutes(edges('F>A', 'F>B', 'A>B', 'F>C', 'F>D'))
    expectClearRoutes(edges('F>A', 'A>B', 'B>C', 'F>C', 'F>B', 'G>C'))
  })

  it('places tables in a join cycle in neighbouring columns, not at the far right', () => {
    const at = layout(edges('A>B', 'B>A', 'B>C')).positions
    expect([at.get('A')?.x, at.get('B')?.x, at.get('C')?.x]).toEqual([0, COLUMN_GAP, 2 * COLUMN_GAP])
  })

  it('gives every table its own spot', () => {
    const { positions } = layout(edges('F>A', 'F>B', 'A>B', 'F>C', 'F>D', 'G>D', 'G>A'))
    const spots = [...positions.values()].map((p) => `${p.x},${p.y}`)
    expect(new Set(spots).size).toBe(spots.length)
  })
})
