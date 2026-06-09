import { useState, useEffect, useRef } from 'react'
import InputBar from './components/InputBar.jsx'
import KnowledgeGraph from './components/KnowledgeGraph.jsx'
import FlowchartGraph from './components/FlowchartGraph.jsx'
import NodeDetail from './components/NodeDetail.jsx'
import StatusPanel from './components/StatusPanel.jsx'
import TourPanel from './components/TourPanel.jsx'

export default function App() {
  const [jobId, setJobId] = useState(null)
  const [status, setStatus] = useState(null)
  const [graph, setGraph] = useState(null)
  const [selectedNode, setSelectedNode] = useState(null)
  const [view, setView] = useState('kg') // 'kg' | 'flow'
  const [tourActive, setTourActive] = useState(false)
  const [tourStep, setTourStep] = useState(0)
  const [highlightedNodeId, setHighlightedNodeId] = useState(null)
  const pollRef = useRef(null)

  useEffect(() => {
    if (!jobId) return
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch(`/api/status/${jobId}`)
        const s = await r.json()
        setStatus(s)
        if (s.status === 'complete') {
          clearInterval(pollRef.current)
          const gr = await fetch(`/api/graph/${jobId}`)
          setGraph(await gr.json())
        } else if (s.status === 'failed') {
          clearInterval(pollRef.current)
        }
      } catch (e) {
        console.error(e)
      }
    }, 1500)
    return () => clearInterval(pollRef.current)
  }, [jobId])

  const handleAnalyze = async (source, sourceType) => {
    setGraph(null)
    setSelectedNode(null)
    setTourActive(false)
    setStatus({ status: 'queued', progress: 0, stage: 'queued' })
    const r = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source, source_type: sourceType }),
    })
    const { job_id } = await r.json()
    setJobId(job_id)
  }

  const handleNodeClick = async (nodeId) => {
    const node = graph.nodes.find((n) => n.id === nodeId)
    if (!node) return
    setSelectedNode({ ...node, loadingDetail: !node.detail })
    setHighlightedNodeId(nodeId)
    if (!node.detail) {
      try {
        const r = await fetch('/api/node_detail', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ job_id: jobId, node_id: nodeId }),
        })
        const data = await r.json()
        node.detail = data.detail
        setSelectedNode({ ...node, loadingDetail: false })
      } catch (e) {
        setSelectedNode({ ...node, loadingDetail: false, detail: `(error: ${e.message})` })
      }
    }
  }

  // Tour controls
  const startTour = () => {
    if (!graph?.tour?.steps?.length) return
    setTourActive(true)
    setTourStep(0)
    setView('kg')
    const firstNodeId = graph.tour.steps[0].node_id
    setHighlightedNodeId(firstNodeId)
    handleNodeClick(firstNodeId)
  }

  const nextStep = () => {
    if (!graph?.tour?.steps) return
    const next = tourStep + 1
    if (next >= graph.tour.steps.length) {
      // stays on outro
      setTourStep(next)
      setHighlightedNodeId(null)
      return
    }
    setTourStep(next)
    const nodeId = graph.tour.steps[next].node_id
    setHighlightedNodeId(nodeId)
    handleNodeClick(nodeId)
  }

  const prevStep = () => {
    if (tourStep === 0) return
    const prev = tourStep - 1
    setTourStep(prev)
    const nodeId = graph.tour.steps[prev].node_id
    setHighlightedNodeId(nodeId)
    handleNodeClick(nodeId)
  }

  const endTour = () => {
    setTourActive(false)
    setHighlightedNodeId(null)
  }

  return (
    <div className="app">
      <header className="header">
        <h1>
          <span className="logo">⬡</span> CodeGraph
          <span className="tag">multi-agent codebase analyzer</span>
        </h1>
        <InputBar onAnalyze={handleAnalyze} disabled={status && status.status === 'running'} />
      </header>

      {status && status.status !== 'complete' && (
        <StatusPanel status={status} />
      )}

      {graph && (
        <>
          <div className="tabs">
            <button
              className={view === 'kg' ? 'active' : ''}
              onClick={() => setView('kg')}
            >
              🕸  Knowledge Graph
            </button>
            <button
              className={view === 'flow' ? 'active' : ''}
              onClick={() => setView('flow')}
            >
              ➜  Flowchart
            </button>
            <button
              className="tour-btn"
              onClick={startTour}
              disabled={!graph.tour?.steps?.length}
            >
              ▶  Start Guided Tour
            </button>
            <div className="stats">
              {graph.stats.n_files} files · {graph.stats.n_classes} classes ·{' '}
              {graph.stats.n_functions} functions · {graph.stats.n_deps} deps
            </div>
          </div>

          <div className="workspace">
            <div className="graph-panel">
              {view === 'kg' ? (
                <KnowledgeGraph
                  graph={graph}
                  onNodeClick={handleNodeClick}
                  highlightedNodeId={highlightedNodeId}
                />
              ) : (
                <FlowchartGraph
                  flowchart={graph.flowchart}
                  onNodeClick={handleNodeClick}
                  fullGraph={graph}
                  highlightedNodeId={highlightedNodeId}
                />
              )}
            </div>
            <div className="detail-panel">
              {tourActive ? (
                <TourPanel
                  tour={graph.tour}
                  step={tourStep}
                  onNext={nextStep}
                  onPrev={prevStep}
                  onEnd={endTour}
                />
              ) : (
                <NodeDetail
                  node={selectedNode}
                  narrative={view === 'flow' ? graph.flowchart?.narrative : null}
                />
              )}
            </div>
          </div>
        </>
      )}

      {!graph && !status && (
        <div className="welcome">
          <h2>Turn any codebase into a knowledge graph.</h2>
          <p className="welcome-line">
            Paste a GitHub URL or a local path above to start. Six agents run in
            sequence — ingestion, parsing, dependency mapping, layer classification,
            Qwen2.5-Coder documentation, flowchart generation, and a guided tour builder.
          </p>
          <div className="agents-grid">
            <div><span className="step-num">1</span> Ingestion <em>git clone or local</em></div>
            <div><span className="step-num">2</span> Parser <em>AST + regex</em></div>
            <div><span className="step-num">3</span> Dependency <em>graph builder</em></div>
            <div><span className="step-num">4</span> Layer <em>classifier</em></div>
            <div><span className="step-num">5</span> Documentation <em>Qwen2.5-Coder</em></div>
            <div><span className="step-num">6</span> Flowchart <em>process flow</em></div>
            <div><span className="step-num">7</span> Tour <em>walkthrough builder</em></div>
          </div>
          <p className="hint">
            Make sure Ollama is running with <code>qwen2.5-coder:7b</code> pulled.
          </p>
        </div>
      )}
    </div>
  )
}
