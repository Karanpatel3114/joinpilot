import { describe, expect, it } from 'vitest'
import proposals from '../../../shared/fixtures/proposals.json'
import type { Proposal } from '../types/api'
import { layout } from './graphLayout'

const all = proposals as Proposal[]

describe('join graph layout', () => {
  it('puts each table one column after its deepest parent', () => {
    const at = layout(all)
    expect(at.get('VBAP')?.x).toBe(0)
    expect(at.get('VBAK')?.x).toBeGreaterThan(0)
    expect(at.get('KNA1')?.x).toBeGreaterThan(at.get('VBAK')?.x ?? 0)
  })

  it('never leaves a table on the straight line of an edge that skips its column', () => {
    const at = layout(all)
    for (const p of all.filter((x) => x.recommended)) {
      const from = at.get(p.from.split('.')[0])
      const to = at.get(p.to.split('.')[0])
      if (!from || !to || from.y !== to.y) continue
      for (const [table, spot] of at) {
        const between = spot.x > from.x && spot.x < to.x
        expect(between && spot.y === from.y, `${table} sits on ${p.edge_id}`).toBe(false)
      }
    }
  })
})
