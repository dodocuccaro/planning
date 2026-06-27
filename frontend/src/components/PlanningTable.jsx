const STATUS_LABEL = {
  growing:      'In crescita',
  stable:       'Stabile',
  declining:    'In calo',
  discontinued: 'Non ordinare',
  low_volume:   'Non ordinare',
}

function trendColor(pct) {
  if (pct > 5)  return '#16a34a'
  if (pct < -5) return '#dc2626'
  return '#6b7280'
}

function fmtNum(v) {
  if (v == null) return '—'
  return Number(v).toLocaleString('it-IT')
}

function fmtDec(v, digits = 2) {
  if (v == null) return '—'
  return Number(v).toLocaleString('it-IT', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export default function PlanningTable({ cards }) {
  if (!cards?.length) return null

  const hasCost    = cards.some(c => c.unit_cost != null)
  const hasPrice   = cards.some(c => c.unit_price != null)
  const hasMargin  = cards.some(c => c.gross_margin_pct != null)
  const hasRevenue = cards.some(c => c.margin_value != null)

  const totalOrder  = cards.reduce((s, c) => s + (c.recommended_purchase || 0), 0)
  const totalRevenue = hasRevenue
    ? cards.reduce((s, c) => s + (c.margin_value || 0), 0)
    : null

  const optCols = (hasMargin ? 1 : 0) + (hasCost ? 1 : 0) + (hasPrice ? 1 : 0)
  const spanBefore = 6 + optCols

  return (
    <div className="table-block" style={{ marginTop: 16 }}>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Prodotto</th>
              <th>Stato</th>
              <th>Trend</th>
              <th>Media storica</th>
              <th>Previsione</th>
              <th>Stock attuale</th>
              {hasMargin && <th>Margine %</th>}
              {hasCost   && <th>Costo €</th>}
              {hasPrice  && <th>Prezzo €</th>}
              <th className="th-highlight">Da ordinare</th>
              {hasRevenue && <th>Margine atteso €</th>}
            </tr>
          </thead>
          <tbody>
            {cards.map((c, i) => (
              <tr key={i} style={c.recommended_purchase === 0 ? { opacity: 0.5 } : {}}>
                <td className="td-label">{c.label}</td>
                <td className="td-num">{STATUS_LABEL[c.status] ?? c.status ?? '—'}</td>
                <td className="td-num" style={{ color: trendColor(c.trend_pct ?? 0) }}>
                  {c.trend_pct != null
                    ? `${c.trend_pct >= 0 ? '+' : ''}${c.trend_pct.toFixed(1)}%`
                    : '—'}
                </td>
                <td className="td-num">{fmtNum(c.avg_sales)}</td>
                <td className="td-num">{fmtNum(c.forecast_demand)}</td>
                <td className="td-num">{fmtNum(c.current_stock)}</td>
                {hasMargin && (
                  <td className="td-num">
                    {c.gross_margin_pct != null ? `${c.gross_margin_pct.toFixed(0)}%` : '—'}
                  </td>
                )}
                {hasCost && <td className="td-num">{fmtDec(c.unit_cost)}</td>}
                {hasPrice && <td className="td-num">{fmtDec(c.unit_price)}</td>}
                <td className="td-num td-highlight">
                  {fmtNum(c.recommended_purchase ?? 0)}
                </td>
                {hasRevenue && (
                  <td className="td-num">
                    {c.margin_value != null
                      ? fmtNum(Math.round(c.margin_value))
                      : '—'}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="planning-total-row">
              <td className="td-label" colSpan={spanBefore}>Totale</td>
              <td className="td-num td-highlight">{fmtNum(totalOrder)}</td>
              {hasRevenue && (
                <td className="td-num">
                  {totalRevenue != null ? fmtNum(Math.round(totalRevenue)) : '—'}
                </td>
              )}
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  )
}
