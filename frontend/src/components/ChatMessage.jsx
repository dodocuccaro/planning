import { useState } from 'react'
import axios from 'axios'
import { useAuth } from '../hooks/useAuth'
import ChartBlock from './ChartBlock'
import TableBlock from './TableBlock'
import PlanningTable from './PlanningTable'

const BACKEND = import.meta.env.VITE_BACKEND_URL || ''

export default function ChatMessage({ message, onOptionClick }) {
  const { role, content, payload } = message
  const { token } = useAuth()
  const [exporting, setExporting] = useState(false)

  async function handleExport(cards) {
    setExporting(true)
    try {
      const res = await axios.post(
        `${BACKEND}/api/export-planning`,
        { cards },
        { headers: { Authorization: `Bearer ${token}` }, responseType: 'blob' }
      )
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = 'pianificazione_acquisti.xlsx'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      // silent fail — user can retry
    } finally {
      setExporting(false)
    }
  }

  if (role === 'user') {
    return (
      <div className="msg msg-user">
        <div className="msg-bubble msg-bubble-user">{content}</div>
      </div>
    )
  }

  // Assistant message
  const p = payload || {}

  if (p.type === 'clarification') {
    return (
      <div className="msg msg-assistant">
        <div className="msg-bubble msg-bubble-assistant">
          <p className="msg-text">{p.text}</p>

          {p.hint && <p className="clarif-hint">{p.hint}</p>}

          {p.options?.length > 0 && (
            <div className="clarif-options">
              {p.options.map(opt => (
                <button key={opt} className="btn btn-outline clarif-btn" onClick={() => onOptionClick(opt)}>
                  {opt}
                </button>
              ))}
              {p.allow_all && (
                <button className="btn btn-outline clarif-btn" onClick={() => onOptionClick('Entrambe')}>
                  Entrambe
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    )
  }

  const hasPlanningCards = p.cards?.length > 0

  return (
    <div className="msg msg-assistant">
      <div className="msg-bubble msg-bubble-assistant">
        {p.text && (
          <div className="msg-text">
            {p.text.split('\n\n').map((para, i) => (
              <p key={i} style={{ margin: i === 0 ? 0 : '8px 0 0' }}>{para}</p>
            ))}
          </div>
        )}

        {p.chart && <ChartBlock chart={p.chart} />}
        {p.table && <TableBlock table={p.table} />}

        {hasPlanningCards && (
          <>
            <div className="planning-export-bar">
              <button
                className="btn btn-outline btn-sm"
                onClick={() => handleExport(p.cards)}
                disabled={exporting}
              >
                {exporting ? 'Esportando…' : '↓ Esporta Excel'}
              </button>
            </div>
            <PlanningTable cards={p.cards} />
          </>
        )}

        {p.follow_up_suggestions?.length > 0 && (
          <div className="suggestions">
            {p.follow_up_suggestions.map(s => (
              <button
                key={s}
                className="btn btn-ghost suggestion-btn"
                onClick={() => onOptionClick(s)}
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {p.type === 'empty' && <p className="msg-empty">Nessun dato trovato con i filtri specificati.</p>}
      </div>
    </div>
  )
}
