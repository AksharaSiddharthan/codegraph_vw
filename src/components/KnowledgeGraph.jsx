import { useEffect, useRef } from 'react'
import { Network } from 'vis-network/standalone'

// Architectural-layer colour palette
const LAYER_COLORS = {
  entry:    { bg: '#ef4444', border: '#991b1b' },  // red — start here
  api:      { bg: '#0ea5e9', border: '#075985' },  // blue — request entry
  business: { bg: '#10b981', border: '#047857' },  // green — domain logic
  data:     { bg: '#f59e0b', border: '#b45309' },  // amber — storage
  ui:       { bg: '#ec4899', border: '#9d174d' },  // pink — view layer
  util:     { bg: '#a855f7', border: '#6b21a8' },  // purple — helpers
  config:   { bg: '#64748b', border: '#334155' },  // slate — config
  test:     { bg: '#94a3b8', border: '#475569' },  // light slate — tests
  external: { bg: '#7c3aed', border: '#4c1d95' },  // violet — deps
  other:    { bg: '#475569', border: '#1e293b' },
}

const TYPE_SHAPES = {
  file: 'box',
  class: 'dot',
  function: 'dot',
  dependency: 'diamond',
}

const EDGE_COLORS = {
  contains: '#475569',
  imports: '#60a5fa',
  inherits: '#10b981',
  depends_on: '#c084fc',
}

export default function KnowledgeGraph({ graph, onNodeClick, highlightedNodeId }) {
  const containerRef = useRef(null)
  const networkRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current || !graph) return

    const nodes = graph.nodes.map((n) => {
      const layer = n.layer || 'other'
      const colors = LAYER_COLORS[layer] || LAYER_COLORS.other
      const isFile = n.type === 'file'
      return {
        id: n.id,
        label: n.label,
        title: `${n.type}: ${n.label}\nlayer: ${layer}`,
        shape: TYPE_SHAPES[n.type] || 'dot',
        color: {
          background: colors.bg,
          border: colors.border,
          highlight: { background: '#fbbf24', border: '#d97706' },
        },
        font: { color: '#ffffff', size: isFile ? 12 : 11, face: 'system-ui' },
        size: isFile ? 20 : 10,
        borderWidth: 2,
      }
    })

    const edges = graph.edges.map((e, i) => ({
      id: `e${i}`,
      from: e.source,
      to: e.target,
      color: { color: EDGE_COLORS[e.type] || '#475569', opacity: 0.55 },
      arrows: e.type === 'inherits' || e.type === 'imports' || e.type === 'depends_on' ? 'to' : '',
      dashes: e.type === 'depends_on',
      smooth: { type: 'continuous' },
    }))

    const options = {
      physics: {
        enabled: true,
        barnesHut: {
          gravitationalConstant: -10000,
          centralGravity: 0.3,
          springLength: 130,
          springConstant: 0.04,
          damping: 0.09,
        },
        stabilization: { iterations: 250 },
      },
      interaction: { hover: true, tooltipDelay: 200 },
      nodes: { borderWidth: 2 },
    }

    const network = new Network(containerRef.current, { nodes, edges }, options)
    networkRef.current = network

    network.on('click', (params) => {
      if (params.nodes.length) {
        onNodeClick(params.nodes[0])
      }
    })

    return () => {
      network.destroy()
      networkRef.current = null
    }
  }, [graph, onNodeClick])

  // Highlight & focus the tour-selected node
  useEffect(() => {
    if (!networkRef.current || !highlightedNodeId) return
    try {
      networkRef.current.selectNodes([highlightedNodeId])
      networkRef.current.focus(highlightedNodeId, {
        scale: 1.1,
        animation: { duration: 600, easingFunction: 'easeInOutQuad' },
      })
    } catch (e) { /* node may not exist */ }
  }, [highlightedNodeId])

  return (
    <div className="graph-container">
      <div className="legend">
        <div className="legend-title">Architectural Layer</div>
        {Object.entries(LAYER_COLORS).map(([layer, c]) => (
          <div key={layer}><span className="dot" style={{ background: c.bg }} /> {layer}</div>
        ))}
      </div>
      <div ref={containerRef} className="vis-canvas" />
    </div>
  )
}
