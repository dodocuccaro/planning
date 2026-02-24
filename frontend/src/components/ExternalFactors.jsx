import { useState } from 'react'
import { analyze } from '../planner'

const BACKEND_URL = (import.meta.env.VITE_BACKEND_URL || '').replace(/\/$/, '')

const EXAMPLE_FACTORS = [
  '❄️ Heavy snowfall expected in mountain resorts this season',
  '📈 Economic growth expected — higher consumer spending',
  '🎿 New ski resort opening nearby, boosting tourism by 30%',
  '🌡️ Warmer-than-average winter forecast',
  '🎉 Major sports event driving local foot traffic',
  '📉 Recession concerns — consumers cutting discretionary spend',
]

export default function ExternalFactors({ onNext, onBack, uploadedData, onResults }) {
  const [factors, setFactors] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  const handleChipClick = (chip) => {
    const text = chip.replace(/^.+?\s/, '') // strip emoji prefix (handles multi-byte emojis)
    setFactors(prev => prev ? `${prev}\n${text}` : text)
  }

  const handleSubmit = async () => {
    setError(null)
    setLoading(true)
    try {
      const factorsText = factors.trim() || 'No external factors provided.'
      let results
      if (BACKEND_URL) {
        const response = await fetch(`${BACKEND_URL}/api/analyze`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ data: uploadedData, external_factors: factorsText }),
        })
        if (!response.ok) {
          const body = await response.json().catch(async () => ({ error: await response.text().catch(() => '') }))
          throw new Error(body.error || `Backend error (${response.status})`)
        }
        results = await response.json()
      } else {
        results = analyze(uploadedData, factorsText)
      }
      onResults(results)
      onNext()
    } catch (err) {
      setError(err.message || 'Analysis failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="card">
        <div className="analyzing-overlay">
          <div className="spinner" />
          <div className="analyzing-text">Analyzing your data…</div>
          <div className="analyzing-sub">
            {BACKEND_URL ? 'Running AI-powered demand analysis' : 'Running trend-based analysis'}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <h2 className="card-title">External Factors</h2>
      <p className="card-subtitle">
        Tell us about any external conditions that might affect demand this season.
        These will be factored into the purchase recommendations.
      </p>

      {BACKEND_URL ? (
        <div className="alert alert-info" style={{ marginBottom: 16, borderColor: 'var(--green-500)', background: 'var(--green-100)', color: '#15803d' }}>
          <span className="alert-icon">✅</span>
          <div>
            <strong>AI analysis active</strong> — your data will be analyzed by GPT-4o-mini, which will
            correlate external factors with your historical sales to fine-tune recommendations.
          </div>
        </div>
      ) : (
        <div className="alert alert-info" style={{ marginBottom: 16 }}>
          <span className="alert-icon">🤖</span>
          <div>
            <strong>Running in offline mode:</strong> AI analysis is not connected.
            Results use historical trend calculations only.
            See the README to deploy the backend and enable full AI recommendations.
          </div>
        </div>
      )}

      <div className="chat-area">
        {/* AI assistant bubble */}
        <div className="chat-bubble">
          <div className="chat-avatar">🤖</div>
          <div className="chat-bubble-text">
            <p>Hi! I've reviewed your historical data. Before I generate purchase recommendations, are there any <strong>external factors</strong> I should take into account?</p>
            <p style={{ marginTop: 8 }}>Think about: seasonal weather, economic conditions, local events, new competition, tourism trends, or anything else that might affect sales.</p>
          </div>
        </div>
      </div>

      {/* Example chips */}
      <div style={{ marginTop: 24 }}>
        <div className="examples-label">Quick examples — click to add</div>
        <div className="example-chips">
          {EXAMPLE_FACTORS.map((ex) => (
            <button
              key={ex}
              className="example-chip"
              onClick={() => handleChipClick(ex)}
              type="button"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {/* Text input */}
      <div>
        <textarea
          className="factors-textarea"
          placeholder="e.g. Heavy snowfall expected in Roccaraso this winter, driving a 25% increase in ski equipment demand…"
          value={factors}
          onChange={(e) => setFactors(e.target.value)}
          rows={5}
        />
        <p className="factors-hint">
          💡 Be as specific as possible — location, percentage estimates, and timeframes help the AI make better recommendations.
          You can also leave this blank to use only historical data trends.
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="alert alert-error">
          <span className="alert-icon">⚠️</span>
          <span>{error}</span>
        </div>
      )}

      <div className="btn-row">
        <button className="btn btn-secondary" onClick={onBack}>← Back</button>
        <button className="btn btn-primary btn-large" onClick={handleSubmit}>
          <span className="btn-icon">🔍</span>
          Analyze &amp; Generate Recommendations
        </button>
      </div>
    </div>
  )
}
