export default function NodeDetail({ node, narrative }) {
  if (!node && !narrative) {
    return (
      <div className="detail empty">
        <p>Click any node to see details, or click <strong>Start Guided Tour</strong> for a walkthrough.</p>
      </div>
    )
  }

  return (
    <div className="detail">
      {narrative && (
        <div className="narrative-block">
          <h3>📋 Project Flow</h3>
          <p>{narrative}</p>
        </div>
      )}

      {node && (
        <div className="node-block">
          <div className="node-header">
            <span className={`badge badge-${node.type}`}>{node.type}</span>
            {node.layer && <span className={`badge badge-layer-${node.layer}`}>{node.layer}</span>}
            <h2>{node.label}</h2>
          </div>

          <div className="props">
            {node.path && <Row k="Path" v={node.path} />}
            {node.file && <Row k="File" v={node.file} />}
            {node.language && <Row k="Language" v={node.language} />}
            {node.lineno != null && <Row k="Line" v={node.lineno} />}
            {node.bases && node.bases.length > 0 && <Row k="Inherits" v={node.bases.join(', ')} />}
            {node.methods && node.methods.length > 0 && (
              <Row k="Methods" v={node.methods.join(', ')} />
            )}
            {node.args && node.args.length > 0 && <Row k="Args" v={node.args.join(', ')} />}
            {node.is_async && <Row k="Async" v="yes" />}
            {node.n_classes != null && <Row k="Classes in file" v={node.n_classes} />}
            {node.n_functions != null && <Row k="Functions in file" v={node.n_functions} />}
            {node.n_imports != null && <Row k="Imports" v={node.n_imports} />}
            {node.external && <Row k="External" v="yes (npm / pip / etc.)" />}
          </div>

          {node.docstring && (
            <div className="docstring-block">
              <h4>Docstring</h4>
              <pre>{node.docstring}</pre>
            </div>
          )}

          <div className="ai-explanation">
            <h4>AI Explanation <span className="model-tag">qwen2.5-coder</span></h4>
            {node.loadingDetail ? (
              <p className="loading">Generating explanation…</p>
            ) : node.detail ? (
              <p>{node.detail}</p>
            ) : (
              <p className="muted">No explanation yet.</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function Row({ k, v }) {
  return (
    <div className="row">
      <span className="k">{k}</span>
      <span className="v">{String(v)}</span>
    </div>
  )
}
