import '@xyflow/react/dist/style.css'
import {
  Background,
  Controls,
  type Edge,
  MarkerType,
  type Node,
  Position,
  ReactFlow,
} from '@xyflow/react'
import { useMemo, useState } from 'react'
import type { Proposal } from '../types/api'
import { pct } from './format'
import { layout, tableOf } from './graphLayout'
import { useDarkMode } from './useDarkMode'

/** React Flow themes its own nodes (its CSS layer loads after Tailwind's), so only the font is set. */
const NODE_STYLE = { fontFamily: 'var(--font-mono)', fontSize: '0.875rem' }

function edgeColor(p: Proposal): string {
  if (p.status === 'approved') return '#059669'
  if (p.status === 'rejected') return '#e11d48'
  return p.recommended ? '#4f46e5' : '#94a3b8'
}

/** The proposed join graph, left to right from facts to dimensions; recommended joins only
 * unless "show all candidates" is on (the others are dashed). */
export function JoinGraph({
  proposals,
  selected,
  onSelect,
}: {
  proposals: Proposal[]
  selected: string | null
  onSelect: (edgeId: string) => void
}) {
  const [showAll, setShowAll] = useState(false)
  const dark = useDarkMode()
  const { nodes, edges } = useMemo(() => {
    const shown = showAll
      ? proposals
      : proposals.filter((p) => p.recommended || p.status === 'approved' || p.edge_id === selected)
    const positions = layout(shown.length ? shown : proposals)
    const nodes: Node[] = [...positions].map(([table, position]) => ({
      id: table,
      position,
      data: { label: table },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      style: NODE_STYLE,
    }))
    const edges: Edge[] = shown.map((p) => ({
      id: p.edge_id,
      source: tableOf(p.from),
      target: tableOf(p.to),
      label: p.recommended || p.status === 'approved' ? `${p.edge_id} · ${pct(p.score)}` : undefined,
      animated: p.edge_id === selected,
      style: {
        stroke: edgeColor(p),
        strokeWidth: p.edge_id === selected ? 3 : 1.5,
        strokeDasharray: p.recommended ? undefined : '5 5',
      },
      markerEnd: { type: MarkerType.ArrowClosed, color: edgeColor(p) },
    }))
    return { nodes, edges }
  }, [proposals, selected, showAll])
  return (
    <div className="relative h-[28rem] rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <label className="absolute right-3 top-3 z-10 flex items-center gap-2 rounded-md bg-white/90 px-2 py-1 text-xs shadow-sm dark:bg-slate-900/90">
        <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
        Show all candidates
      </label>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onEdgeClick={(_, edge) => onSelect(edge.id)}
        fitView
        className={dark ? 'dark' : 'light'}
        proOptions={{ hideAttribution: true }}
        aria-label="Join graph"
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}
