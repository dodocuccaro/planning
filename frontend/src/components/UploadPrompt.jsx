import { useRef, useState } from 'react'
import axios from 'axios'
import { useAuth } from '../hooks/useAuth'

const BACKEND = import.meta.env.VITE_BACKEND_URL || ''

export default function UploadPrompt({ onParsed }) {
  const { token } = useAuth()
  const inputRef  = useRef(null)
  const [dragging, setDragging]   = useState(false)
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState('')

  async function handleFile(file) {
    if (!file) return
    setError('')
    setLoading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await axios.post(`${BACKEND}/api/parse-excel`, form, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' }
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
    <div className="upload-prompt">
      <div
        className={`dropzone ${dragging ? 'dragging' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls"
          style={{ display: 'none' }}
          onChange={e => handleFile(e.target.files[0])}
        />
        {loading ? (
          <p className="dropzone-text">Analisi del file in corso...</p>
        ) : (
          <>
            <span className="dropzone-icon">📂</span>
            <p className="dropzone-text">
              Trascina qui il file Excel del tuo gestionale<br />
              <span className="dropzone-sub">oppure clicca per scegliere il file (.xlsx, .xls)</span>
            </p>
            <p className="dropzone-hint">
              Il file deve avere le intestazioni delle colonne nella prima riga e almeno 3 anni di dati.
            </p>
          </>
        )}
      </div>
      {error && <p className="upload-error">{error}</p>}
    </div>
  )
}
