import '@xyflow/react/dist/style.css'
import { Background, Controls, type Edge, MarkerType, type Node, ReactFlow } from '@xyflow/react'
import { useMemo } from 'react'
import type { Proposal } from '../types/api'
import { pct } from './format'

const COLUMN_GAP = 280
const ROW_GAP = 110

/** Place tables in columns by how deep they sit in the recommended join graph. */
function layout(proposals: Proposal[]): Map<string, { x: number; y: number }> {
  const tables = new Set<string>()
  for (const p of proposals) {
    tables.add(p.from.split('.')[0])
    tables.add(p.to.split('.')[0])
  }
  const depth = new Map<string, number>([...tables].map((t) => [t, 0]))
  const edges = proposals.filter((p) => p.recommended)
  for (let i = 0; i < tables.size; i += 1) {
    for (const p of edges) {
      const from = p.from.split('.')[0]
      const to = p.to.split('.')[0]
      depth.set(to, Math.max(depth.get(to) ?? 0, (depth.get(from) ?? 0) + 1))
    }
  }
  const rows = new Map<number, number>()
  const positions = new Map<string, { x: number; y: number }>()
  for (const table of [...tables].sort()) {
    const column = Math.min(depth.get(table) ?? 0, tables.size)
    const row = rows.get(column) ?? 0
    rows.set(column, row + 1)
    positions.set(table, { x: column * COLUMN_GAP, y: row * ROW_GAP })
  }
  return positions
}

function edgeColor(p: Proposal): string {
  if (p.status === 'approved') return '#059669'
  if (p.status === 'rejected') return '#e11d48'
  return p.recommended ? '#4f46e5' : '#94a3b8'
}

/** The proposed join graph; recommended joins are solid, the others dashed. */
export function JoinGraph({
  proposals,
  selected,
  onSelect,
}: {
  proposals: Proposal[]
  selected: string | null
  onSelect: (edgeId: string) => void
}) {
  const { nodes, edges } = useMemo(() => {
    const positions = layout(proposals)
    const nodes: Node[] = [...positions].map(([table, position]) => ({
      id: table,
      position,
      data: { label: table },
      className: 'rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-sm shadow-sm',
    }))
    const edges: Edge[] = proposals.map((p) => ({
      id: p.edge_id,
      source: p.from.split('.')[0],
      target: p.to.split('.')[0],
      label: `${p.edge_id} · ${pct(p.score)}`,
      animated: p.edge_id === selected,
      style: {
        stroke: edgeColor(p),
        strokeWidth: p.edge_id === selected ? 3 : 1.5,
        strokeDasharray: p.recommended ? undefined : '5 5',
      },
      markerEnd: { type: MarkerType.ArrowClosed, color: edgeColor(p) },
    }))
    return { nodes, edges }
  }, [proposals, selected])
  return (
    <div className="h-[28rem] rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onEdgeClick={(_, edge) => onSelect(edge.id)}
        fitView
        proOptions={{ hideAttribution: true }}
        aria-label="Join graph"
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}
