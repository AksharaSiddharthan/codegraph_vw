import { useEffect, useRef } from 'react'
import { Network } from 'vis-network/standalone'

// Same palette as KG so user can mentally map across views
const LAYER_COLORS = {
  entry:    { bg: '#ef4444', border: '#991b1b' },
  api:      { bg: '#0ea5e9', border: '#075985' },
  business: { bg: '#10b981', border: '#047857' },
  data:     { bg: '#f59e0b', border: '#b45309' },
  ui:       { bg: '#ec4899', border: '#9d174d' },
  util:     { bg: '#a855f7', border: '#6b21a8' },
  config:   { bg: '#64748b', border: '#334155' },
  test:     { bg: '#94a3b8', border: '#475569' },
  other:    { bg: '#475569', border: '#1e293b' },
}

// Lane order maps to "level" in vis-network hierarchical layout
const LANE_LEVEL = {
  entry: 0, api: 1, business: 2, data: 3, ui: 4, util: 5, config: 6, test: 7, other: 8,
}

export default function FlowchartGraph({ flowchart, onNodeClick, fullGraph, highlightedNodeId }) {
  const containerRef = useRef(null)
  const networkRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current || !flowchart) return

    const nodes = flowchart.nodes.map((n) => {
      const colors = LAYER_COLORS[n.lane] || LAYER_COLORS.other
      return {
        id: n.id,
        label: `${n.label}\n[${n.lane}]`,
        title: `${n.path}\nLane: ${n.lane}${n.is_entry ? ' (entry point)' : ''}`,
        shape: n.is_entry ? 'star' : 'box',
        color: {
          background: colors.bg,
          border: colors.border,
          highlight: { background: '#fbbf24', border: '#d97706' },
        },
        font: { color: '#0b1220', size: 11, multi: 'html', face: 'system-ui' },
        level: LANE_LEVEL[n.lane] ?? 8,
        size: n.is_entry ? 28 : 18,
        borderWidth: 2,
      }
    })

    const edges = flowchart.edges.map((e, i) => ({
      id: `fe${i}`,
      from: e.source,
      to: e.target,
      label: e.label,
      arrows: 'to',
      color: { color: '#64748b' },
      font: { color: '#cbd5e1', size: 9, strokeWidth: 0, align: 'middle' },
      smooth: { type: 'cubicBezier', forceDirection: 'horizontal', roundness: 0.4 },
    }))

    const options = {
      layout: {
        hierarchical: {
          enabled: true,
          direction: 'LR',
          sortMethod: 'directed',
          nodeSpacing: 150,
          levelSeparation: 230,
          treeSpacing: 200,
        },
      },
      physics: { enabled: false },
      interaction: { hover: true, tooltipDelay: 200 },
    }

    const network = new Network(containerRef.current, { nodes, edges }, options)
    networkRef.current = network

    network.on('click', (params) => {
      if (params.nodes.length) {
        const flowNode = flowchart.nodes.find((n) => n.id === params.nodes[0])
        if (flowNode) {
          const fileNodeId = `file::${flowNode.path}`
          if (fullGraph.nodes.find((n) => n.id === fileNodeId)) {
            onNodeClick(fileNodeId)
          }
        }
      }
    })

    return () => network.destroy()
  }, [flowchart, onNodeClick, fullGraph])

  // Focus on highlighted node from tour
  useEffect(() => {
    if (!networkRef.current || !highlightedNodeId) return
    // Try to map a file node back to its flowchart node
    const path = highlightedNodeId.replace('file::', '')
    const flowId = `flow::${path}`
    try {
      networkRef.current.selectNodes([flowId])
      networkRef.current.focus(flowId, {
        scale: 1.0,
        animation: { duration: 600, easingFunction: 'easeInOutQuad' },
      })
    } catch (e) { /* not in flowchart */ }
  }, [highlightedNodeId])

  // Layers actually present in the flowchart, for the legend
  const lanesPresent = Array.from(new Set(flowchart?.nodes.map((n) => n.lane) || []))

  return (
    <div className="graph-container">
      <div className="legend">
        <div className="legend-title">Layers in this flow</div>
        {lanesPresent.map((lane) => (
          <div key={lane}>
            <span className="dot" style={{ background: LAYER_COLORS[lane]?.bg || '#475569' }} />
            {lane}
          </div>
        ))}
        <div className="legend-divider" />
        <div><span className="star">★</span> entry point</div>
      </div>
      <div ref={containerRef} className="vis-canvas" />
    </div>
  )
}
