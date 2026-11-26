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
import { RoutedEdge } from './RoutedEdge'
import { useDarkMode } from './useDarkMode'

const EDGE_TYPES = { routed: RoutedEdge }

/** React Flow themes its own nodes (its CSS layer loads after Tailwind's), so only the font is set. */
const NODE_STYLE = { fontFamily: 'var(--font-mono)', fontSize: '0.875rem', borderRadius: '10px' }

/** Edge colours: approved green, rejected red, recommended in the theme's ink, others grey. */
function edgeColor(p: Proposal, dark: boolean): string {
  if (p.status === 'approved') return dark ? '#8fcb63' : '#33701d'
  if (p.status === 'rejected') return dark ? '#fb7185' : '#e11d48'
  if (p.recommended) return dark ? '#bfe988' : '#1b2811'
  return dark ? '#6b7064' : '#a3a89b'
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
    const { positions, waypoints } = layout(shown.length ? shown : proposals)
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
      ...(waypoints.has(p.edge_id) && {
        type: 'routed',
        data: { waypoints: waypoints.get(p.edge_id), origin: positions.get(tableOf(p.from)) },
      }),
      source: tableOf(p.from),
      target: tableOf(p.to),
      label: p.recommended || p.status === 'approved' ? `${p.edge_id} · ${pct(p.score)}` : undefined,
      animated: p.edge_id === selected,
      style: {
        stroke: edgeColor(p, dark),
        strokeWidth: p.edge_id === selected ? 3 : 1.5,
        strokeDasharray: p.recommended ? undefined : '5 5',
      },
      markerEnd: { type: MarkerType.ArrowClosed, color: edgeColor(p, dark) },
    }))
    return { nodes, edges }
  }, [proposals, selected, showAll, dark])
  return (
    <div className="relative h-[28rem] rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <label className="absolute right-3 top-3 z-10 flex items-center gap-2 rounded-md bg-white/90 px-2 py-1 font-mono text-[11px] shadow-sm dark:bg-slate-900/90">
        <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
        Show all candidates
      </label>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        edgeTypes={EDGE_TYPES}
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
