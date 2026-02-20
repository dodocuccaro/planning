import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'

function TrendBadge({ trendPct }) {
  const cls = trendPct > 0 ? 'trend-positive' : trendPct < 0 ? 'trend-negative' : 'trend-neutral'
  const arrow = trendPct > 0 ? '↑' : trendPct < 0 ? '↓' : '→'
  return (
    <span className={`metric-value ${cls}`}>
      {arrow} {Math.abs(trendPct).toFixed(1)}%
    </span>
  )
}

function AdjustmentBadge({ factor }) {
  const pct = ((factor - 1) * 100).toFixed(0)
  const cls = factor > 1 ? 'adjustment-positive' : factor < 1 ? 'adjustment-negative' : 'adjustment-neutral'
  const label = factor > 1 ? `+${pct}%` : factor < 1 ? `${pct}%` : 'Neutral'
  return <span className={`adjustment-badge ${cls}`}>{label} AI adjustment</span>
}

const CHART_COLORS = ['#4aa3e8', '#2589d4', '#1d6daa', '#1a4d7c']

function SalesChart({ years, sales }) {
  const data = years.map((yr, i) => ({ year: String(yr), sales: sales[i] }))
  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis dataKey="year" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} width={48} />
        <Tooltip
          formatter={(v) => [v.toLocaleString(), 'Units Sold']}
          contentStyle={{ borderRadius: 8, fontSize: 13 }}
        />
        <Bar dataKey="sales" radius={[4, 4, 0, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function ProductCard({ product }) {
  const {
    product_code, product_name, sales_channel, years, historical_sales,
    avg_sales, trend_pct, adjustment_factor, recommended_purchase, ai_reasoning,
  } = product

  return (
    <div className="product-card">
      <div className="product-card-header">
        <div className="product-name-block">
          <div className="product-name">{product_name}</div>
          <div className="product-code">
            Code: {product_code}
            {sales_channel ? <span className="channel-badge">🏪 {sales_channel}</span> : null}
          </div>
        </div>
        <div className="product-rec">
          <div className="rec-label">Recommended Order</div>
          <div className="rec-value">{recommended_purchase.toLocaleString()}</div>
          <div className="rec-unit">units</div>
        </div>
      </div>

      <div className="product-card-body">
        {/* Chart */}
        <div className="chart-section">
          <h4>Historical Sales</h4>
          <SalesChart years={years} sales={historical_sales} />
        </div>

        {/* Metrics */}
        <div className="metrics-panel">
          <div className="metric-item">
            <div className="metric-label">Avg Annual Sales</div>
            <div className="metric-value">{avg_sales.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
          </div>
          <div className="metric-item">
            <div className="metric-label">Sales Trend</div>
            <TrendBadge trendPct={trend_pct} />
          </div>
          <div className="metric-item">
            <div className="metric-label">AI Adjustment</div>
            <AdjustmentBadge factor={adjustment_factor} />
          </div>
          <div className="metric-item">
            <div className="metric-label">Safety Buffer</div>
            <span className="metric-value" style={{ color: 'var(--amber-500)' }}>+10%</span>
          </div>
        </div>

        {/* AI Reasoning */}
        {ai_reasoning && (
          <div className="ai-reasoning">
            <div className="ai-reasoning-label">🤖 AI Reasoning</div>
            {ai_reasoning}
          </div>
        )}
      </div>
    </div>
  )
}

export default function Results({ results, onBack, onRestart }) {
  if (!results) {
    return (
      <div className="card">
        <div className="alert alert-error">
          <span className="alert-icon">⚠️</span>
          <span>No results available. Please go back and try again.</span>
        </div>
        <div className="btn-row">
          <button className="btn btn-secondary" onClick={onBack}>← Back</button>
        </div>
      </div>
    )
  }

  const { products, ai_adjustment, external_factors } = results
  const totalRecommended = products.reduce((sum, p) => sum + p.recommended_purchase, 0)
  const aiActive = ai_adjustment?.relevant_data_found

  return (
    <div>
      {/* Summary bar */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h2 className="card-title">Purchase Recommendations</h2>
        <p className="card-subtitle" style={{ marginBottom: 20 }}>
          Based on your historical data{external_factors && external_factors !== 'No external factors provided.' ? ' and the external factors you described' : ''}.
        </p>

        <div className="results-summary">
          <div className="summary-card">
            <div className="big-number">{products.length}</div>
            <div className="summary-label">Products Analyzed</div>
          </div>
          <div className="summary-card">
            <div className="big-number">{totalRecommended.toLocaleString()}</div>
            <div className="summary-label">Total Units to Order</div>
          </div>
          <div className="summary-card">
            <div className="big-number" style={{ color: aiActive ? 'var(--green-500)' : 'var(--gray-500)', fontSize: '1.4rem' }}>
              {aiActive ? '✓ Active' : '○ Off'}
            </div>
            <div className="summary-label">AI Adjustment</div>
          </div>
          <div className="summary-card">
            <div className="big-number" style={{ fontSize: '1.4rem' }}>
              {ai_adjustment?.adjustment_factor != null
                ? `×${Number(ai_adjustment.adjustment_factor).toFixed(2)}`
                : '×1.00'}
            </div>
            <div className="summary-label">Demand Multiplier</div>
          </div>
        </div>

        {/* External factors echo */}
        {external_factors && external_factors !== 'No external factors provided.' && (
          <div className="alert alert-info" style={{ marginBottom: 0 }}>
            <span className="alert-icon">🌍</span>
            <div>
              <strong>External factors considered:</strong>{' '}
              {external_factors}
            </div>
          </div>
        )}
      </div>

      {/* Per-product cards */}
      <div className="product-cards">
        {products.map((p) => (
          <ProductCard key={`${p.product_code}|||${p.sales_channel || ''}`} product={p} />
        ))}
      </div>

      <div className="btn-row" style={{ marginTop: 32 }}>
        <button className="btn btn-secondary" onClick={onBack}>← Back</button>
        <button className="btn btn-primary" onClick={onRestart}>
          🔄 New Analysis
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => {
            const json = JSON.stringify(results, null, 2)
            const blob = new Blob([json], { type: 'application/json' })
            const url  = URL.createObjectURL(blob)
            const a    = document.createElement('a')
            a.href     = url
            a.download = 'planning_results.json'
            a.click()
            URL.revokeObjectURL(url)
          }}
        >
          ⬇️ Export JSON
        </button>
      </div>
    </div>
  )
}
