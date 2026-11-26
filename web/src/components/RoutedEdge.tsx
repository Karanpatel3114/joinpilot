import { BaseEdge, type Edge, type EdgeProps } from '@xyflow/react'
import type { Point } from './graphLayout'

export type RoutedEdgeType = Edge<{ waypoints: Point[]; origin: Point }, 'routed'>

/** A smooth curve from (x1, y1) to (x2, y2) that leaves and arrives horizontally. */
function curve(x1: number, y1: number, x2: number, y2: number): string {
  const c = (x2 - x1) / 2
  return `C ${x1 + c} ${y1} ${x2 - c} ${y2} ${x2} ${y2}`
}

/** An edge that skips columns, drawn through the empty slots the layout reserved for it so
 * it never crosses another table. `origin` is the source node's corner, which gives the
 * handle's offset inside a node. */
export function RoutedEdge({ sourceX, sourceY, targetX, targetY, data, label, ...rest }: EdgeProps<RoutedEdgeType>) {
  const points = data?.waypoints ?? []
  const origin = data?.origin ?? { x: sourceX, y: sourceY }
  const width = sourceX - origin.x
  const dy = sourceY - origin.y
  let path = `M ${sourceX} ${sourceY}`
  let [x, y] = [sourceX, sourceY]
  for (const p of points) {
    path += ` ${curve(x, y, p.x, p.y + dy)} L ${p.x + width} ${p.y + dy}`
    ;[x, y] = [p.x + width, p.y + dy]
  }
  path += ` ${curve(x, y, targetX, targetY)}`
  const middle = points[Math.floor(points.length / 2)]
  return (
    <BaseEdge
      path={path}
      label={label}
      labelX={middle ? middle.x + width / 2 : (sourceX + targetX) / 2}
      labelY={middle ? middle.y + dy : (sourceY + targetY) / 2}
      style={rest.style}
      markerEnd={rest.markerEnd}
      interactionWidth={rest.interactionWidth}
    />
  )
}
