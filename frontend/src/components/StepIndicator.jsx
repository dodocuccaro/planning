export default function StepIndicator({ steps, currentStep }) {
  return (
    <nav className="step-indicator" aria-label="Progress">
      {steps.map((step, idx) => {
        const isCompleted = step.id < currentStep
        const isActive    = step.id === currentStep
        return (
          <div key={step.id} style={{ display: 'flex', alignItems: 'center', flex: idx < steps.length - 1 ? 1 : 'none' }}>
            <div className={`step-item ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}>
              <div className="step-circle">
                {isCompleted ? '✓' : step.id}
              </div>
              <span className="step-label">{step.label}</span>
            </div>
            {idx < steps.length - 1 && (
              <div className={`step-connector ${isCompleted ? 'completed' : ''}`} />
            )}
          </div>
        )
      })}
    </nav>
  )
}
