import { useState } from 'react'
import axios from 'axios'
import { useAuth } from '../hooks/useAuth'

const BACKEND = import.meta.env.VITE_BACKEND_URL || ''

const FIELD_LABELS = {
  product_id:       'Codice prodotto',
  product_name:     'Nome prodotto',
  color:            'Colore',
  size:             'Taglia',
  category:         'Categoria',
  supplier_name:    'Fornitore',
  supplier_code:    'Codice fornitore',
  sales_channel:    'Canale vendita',
  unit_cost:        'Costo unitario',
  currency:         'Valuta',
  unit_of_measure:  'Unità di misura',
  current_stock:    'Stock attuale',
  opening_stock:    'Giacenza inizio anno',
  qty_purchased:    'Quantità acquistata',
  closing_stock:    'Giacenza fine anno',
  qty_sold:         'Quantità venduta',
  year_data:        '(dati annuali)',
}

const ALL_FIELDS = Object.keys(FIELD_LABELS).filter(f => f !== 'year_data')

export default function ColumnMappingConfirm({ parseResult, onConfirmed }) {
  const { token } = useAuth()

  const [mapping, setMapping]   = useState(parseResult.mapping || {})
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  const nonYearCols = Object.entries(mapping).filter(([, v]) => v !== 'year_data')
  const yearGroups  = parseResult.year_groups || {}
  const confidence  = parseResult.confidence  || {}

  function updateMapping(col, newField) {
    setMapping(prev => ({ ...prev, [col]: newField }))
  }

  async function handleConfirm() {
    setError('')
    setLoading(true)
    try {
      const res = await axios.post(
        `${BACKEND}/api/parse-excel/confirm`,
        {
          session_id:  parseResult.session_id,
          mapping,
          year_groups: yearGroups,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      onConfirmed(res.data)
    } catch (err) {
      setError(err.response?.data?.error || 'Errore nella conferma del mapping.')
    } finally {
      setLoading(false)
    }
  }

  const hasMissingRequired = (parseResult.missing_required || []).length > 0

  return (
    <div className="mapping-confirm">
      <h3>Verifica il riconoscimento delle colonne</h3>
      <p className="mapping-subtitle">
        Il sistema ha identificato automaticamente le colonne del tuo file.
        Correggi eventuali errori prima di procedere.
      </p>

      {hasMissingRequired && (
        <div className="mapping-warning">
          Codice/nome prodotto non rilevati automaticamente ({parseResult.missing_required.join(', ')}).
          Se il tuo file usa una colonna categoria come identificatore (es. "Gruppo Merce"),
          puoi procedere comunque — il sistema la userà come nome prodotto.
          Altrimenti assegna manualmente il campo corretto dal menu a tendina.
        </div>
      )}

      <div className="mapping-table">
        <div className="mapping-row mapping-header">
          <span>Colonna nel file</span>
          <span>Campo rilevato</span>
          <span>Confidenza</span>
        </div>
        {nonYearCols.map(([col, field]) => {
          const conf = confidence[col] || 0
          const confClass = conf >= 0.85 ? 'conf-high' : conf >= 0.7 ? 'conf-mid' : 'conf-low'
          return (
            <div key={col} className="mapping-row">
              <span className="col-original">{col}</span>
              <select
                value={field}
                onChange={e => updateMapping(col, e.target.value)}
                className="col-select"
              >
                <option value="">— non usare —</option>
                {ALL_FIELDS.map(f => (
                  <option key={f} value={f}>{FIELD_LABELS[f]}</option>
                ))}
              </select>
              <span className={`conf-badge ${confClass}`}>
                {Math.round(conf * 100)}%
              </span>
            </div>
          )
        })}
      </div>

      {Object.keys(yearGroups).length > 0 && (
        <div className="year-groups-summary">
          <strong>Anni rilevati:</strong>{' '}
          {Object.keys(yearGroups).sort().join(', ')}
          {' '}({Object.keys(yearGroups).length} anni di dati)
        </div>
      )}

      {error && <p className="mapping-error">{error}</p>}

      <button
        className="btn btn-primary"
        onClick={handleConfirm}
        disabled={loading}
      >
        {loading ? 'Caricamento...' : 'Conferma e inizia'}
      </button>
    </div>
  )
}
