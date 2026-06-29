import { useRef, useState } from 'react'
import axios from 'axios'
import { useAuth } from '../hooks/useAuth'

const BACKEND = import.meta.env.VITE_BACKEND_URL || ''

function IconSpreadsheet() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18M3 15h18M9 3v18" />
    </svg>
  )
}

function IconPlug() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 22v-5M9 8V2M15 8V2" />
      <rect x="4" y="8" width="16" height="6" rx="2" />
    </svg>
  )
}

function IconUpload() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17,8 12,3 7,8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  )
}

function IconArrow() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 12h14M12 5l7 7-7 7" />
    </svg>
  )
}

function IconLock() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  )
}

export default function DataSourcePicker({ onParsed }) {
  const { token } = useAuth()
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleFile(file) {
    if (!file) return
    setError('')
    setLoading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await axios.post(`${BACKEND}/api/parse-excel`, form, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' },
      })
      onParsed(res.data)
    } catch (err) {
      setError(err.response?.data?.error || 'Errore durante il caricamento del file.')
    } finally {
      setLoading(false)
    }
  }

  function onDrop(e) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  return (
    <div className="source-picker">
      {/* ── Card 1: Excel upload ───────────────────────────────────────────── */}
      <div
        className={`source-card source-card-excel${dragging ? ' source-card-dragging' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !loading && inputRef.current?.click()}
        style={{ cursor: loading ? 'default' : 'pointer' }}
        role="button"
        tabIndex={0}
        aria-label="Carica file Excel"
        onKeyDown={e => e.key === 'Enter' && !loading && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls"
          style={{ display: 'none' }}
          onChange={e => handleFile(e.target.files[0])}
        />

        <div className="source-icon source-icon-excel">
          <IconSpreadsheet />
        </div>

        <div>
          <div className="source-title">Carica da Excel</div>
          <div className="source-desc">
            Esporta i dati dal tuo gestionale e caricali qui. Il sistema rileva automaticamente le colonne.
          </div>
        </div>

        <div className="source-chips">
          {['.xlsx', '.xls', 'multi-sheet', 'auto-mapping'].map(t => (
            <span key={t} className="source-chip">{t}</span>
          ))}
        </div>

        <div className="source-upload-area">
          <IconUpload />
          <span>
            {loading
              ? 'Analisi in corso…'
              : dragging
              ? 'Rilascia il file qui'
              : 'Trascina il file o clicca per sfogliare'}
          </span>
        </div>

        {error && <p className="upload-error" style={{ margin: 0 }}>{error}</p>}
      </div>

      {/* ── Card 2: ERP — coming soon ──────────────────────────────────────── */}
      <div className="source-card source-card-erp" aria-label="Connetti gestionale — disponibile a breve">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div className="source-icon source-icon-erp">
            <IconPlug />
          </div>
          <span className="source-badge-coming">
            <IconLock />
            Prossimamente
          </span>
        </div>

        <div>
          <div className="source-title">Connetti Gestionale</div>
          <div className="source-desc">
            Integrazione diretta con il tuo software di magazzino. Nessun export manuale — i dati si sincronizzano in automatico.
          </div>
        </div>

        <div className="source-chips">
          {['Atelier', 'Stealth', 'TeamSystem', 'API REST'].map(t => (
            <span key={t} className="source-chip source-chip-erp">{t}</span>
          ))}
        </div>

        <div className="source-cta source-cta-erp">
          <span>Scopri di più</span>
          <IconArrow />
        </div>
      </div>
    </div>
  )
}
