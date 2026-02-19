import { useState } from 'react'
import StepIndicator from './components/StepIndicator'
import TemplateDownload from './components/TemplateDownload'
import FileUpload from './components/FileUpload'
import ExternalFactors from './components/ExternalFactors'
import Results from './components/Results'

const STEPS = [
  { id: 1, label: 'Download Template', icon: '⬇️' },
  { id: 2, label: 'Upload Data',       icon: '📤' },
  { id: 3, label: 'External Factors',  icon: '🌍' },
  { id: 4, label: 'Results',           icon: '📊' },
]

export default function App() {
  const [currentStep, setCurrentStep] = useState(1)
  const [uploadedData, setUploadedData]   = useState(null)
  const [analysisResults, setAnalysisResults] = useState(null)

  const goNext = () => setCurrentStep(s => Math.min(s + 1, 4))
  const goBack = () => setCurrentStep(s => Math.max(s - 1, 1))
  const restart = () => {
    setCurrentStep(1)
    setUploadedData(null)
    setAnalysisResults(null)
  }

  return (
    <div className="app-wrapper">
      {/* Header */}
      <header className="app-header">
        <div className="header-inner">
          <div className="header-brand">
            <span className="header-icon">📦</span>
            <div>
              <h1 className="header-title">Retail Planning Tool</h1>
              <p className="header-subtitle">AI-powered purchase recommendations</p>
            </div>
          </div>
          {currentStep > 1 && (
            <button className="btn btn-ghost" onClick={restart}>
              ↩ Start Over
            </button>
          )}
        </div>
      </header>

      {/* Step indicator */}
      <div className="step-indicator-wrapper">
        <StepIndicator steps={STEPS} currentStep={currentStep} />
      </div>

      {/* Main content */}
      <main className="main-content">
        <div className="step-container">
          {currentStep === 1 && (
            <TemplateDownload onNext={goNext} />
          )}
          {currentStep === 2 && (
            <FileUpload
              onNext={goNext}
              onBack={goBack}
              onDataLoaded={setUploadedData}
            />
          )}
          {currentStep === 3 && (
            <ExternalFactors
              onNext={goNext}
              onBack={goBack}
              uploadedData={uploadedData}
              onResults={setAnalysisResults}
            />
          )}
          {currentStep === 4 && (
            <Results
              results={analysisResults}
              onBack={goBack}
              onRestart={restart}
            />
          )}
        </div>
      </main>

      <footer className="app-footer">
        <p>Retail Planning Tool — Powered by AI &amp; Data Analytics</p>
      </footer>
    </div>
  )
}
