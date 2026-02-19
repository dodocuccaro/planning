import { useState } from 'react'
import axios from 'axios'

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
    const text = chip.replace(/^[\S]+ /, '') // strip emoji prefix
    setFactors(prev => prev ? `${prev}\n${text}` : text)
  }

  const handleSubmit = async () => {
    setError(null)
    setLoading(true)
    try {
      const res = await axios.post('/api/analyze', {
        data: uploadedData,
        external_factors: factors.trim() || 'No external factors provided.',
      })
      onResults(res.data)
      onNext()
    } catch (err) {
      const msg = err.response?.data?.error || 'Analysis failed. Please try again.'
      setError(msg)
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
          <div className="analyzing-sub">Running AI-powered demand analysis</div>
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <h2 className="card-title">External Factors</h2>
      <p className="card-subtitle">
        Tell us about any external conditions that might affect demand this season.
        The AI will factor these into its purchase recommendations.
      </p>

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
