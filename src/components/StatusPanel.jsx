const STAGE_LABELS = {
  queued: 'Queued…',
  ingesting: 'Agent 1: Ingesting repository',
  parsing: 'Agent 2: Parsing source files (AST)',
  mapping_dependencies: 'Agent 3: Mapping dependencies',
  classifying_layers: 'Agent 4: Classifying architectural layers',
  generating_docs: 'Agent 5: Generating docs (Qwen2.5-Coder)',
  building_flowchart: 'Agent 6: Building flowchart',
  generating_tour: 'Agent 7: Generating guided tour',
  complete: 'Complete',
}

export default function StatusPanel({ status }) {
  return (
    <div className="status-panel">
      {status.status === 'failed' ? (
        <div className="error">
          <strong>Pipeline failed.</strong>
          <pre>{status.error}</pre>
        </div>
      ) : (
        <>
          <div className="stage-label">{STAGE_LABELS[status.stage] || status.stage}</div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${status.progress}%` }} />
          </div>
          <div className="progress-text">{status.progress}%</div>
        </>
      )}
    </div>
  )
}
