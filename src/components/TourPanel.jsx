export default function TourPanel({ tour, step, onNext, onPrev, onEnd }) {
  if (!tour || !tour.steps) return null

  const total = tour.steps.length
  const isIntro = step === -1   // not used currently but reserved
  const isOutro = step >= total
  const currentStep = !isOutro ? tour.steps[step] : null

  return (
    <div className="tour">
      <div className="tour-header">
        <div className="tour-title">
          🧭 Guided Tour
        </div>
        <button className="tour-end" onClick={onEnd} title="Exit tour">✕</button>
      </div>

      {step === 0 && tour.intro && (
        <div className="tour-intro">
          <em>{tour.intro}</em>
        </div>
      )}

      {!isOutro && currentStep && (
        <div className="tour-step">
          <div className="tour-progress">
            <div className="tour-progress-bar">
              <div
                className="tour-progress-fill"
                style={{ width: `${((step + 1) / total) * 100}%` }}
              />
            </div>
            <div className="tour-progress-text">
              Step {step + 1} of {total}
            </div>
          </div>

          <div className="tour-node">
            <span className={`badge badge-layer-${currentStep.layer}`}>
              {currentStep.layer}
            </span>
            <h3>{currentStep.node_label}</h3>
            {currentStep.path && <div className="tour-path">{currentStep.path}</div>}
          </div>

          <div className="tour-narration">
            {currentStep.narration}
          </div>
        </div>
      )}

      {isOutro && (
        <div className="tour-outro">
          <h3>Tour complete 🎉</h3>
          <p>{tour.outro}</p>
        </div>
      )}

      <div className="tour-controls">
        <button onClick={onPrev} disabled={step === 0}>← Previous</button>
        {!isOutro ? (
          <button className="primary" onClick={onNext}>
            {step + 1 === total ? 'Finish' : 'Next →'}
          </button>
        ) : (
          <button className="primary" onClick={onEnd}>Close tour</button>
        )}
      </div>
    </div>
  )
}
