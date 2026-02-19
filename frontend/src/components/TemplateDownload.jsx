const TEMPLATE_URL = `${import.meta.env.BASE_URL}planning_template.xlsx`

export default function TemplateDownload({ onNext }) {
  const handleDownload = () => {
    const link = document.createElement('a')
    link.href = TEMPLATE_URL
    link.download = 'planning_template.xlsx'
    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  return (
    <div className="card">
      <div className="template-hero">
        <div className="template-hero-icon">📋</div>
        <h2 className="card-title">Download the Planning Template</h2>
        <p className="card-subtitle">
          Start by downloading our Excel template. Fill it in with your historical
          purchasing and stock data, then come back to upload it.
        </p>
      </div>

      <div className="feature-list">
        <div className="feature-item">
          <span className="feature-icon">📦</span>
          <div className="feature-text">
            <strong>Multi-product support</strong>
            <span>Plan for as many products as you need in one file</span>
          </div>
        </div>
        <div className="feature-item">
          <span className="feature-icon">📅</span>
          <div className="feature-text">
            <strong>Multi-year history</strong>
            <span>Enter 2–3+ years of data for more accurate forecasts</span>
          </div>
        </div>
        <div className="feature-item">
          <span className="feature-icon">💡</span>
          <div className="feature-text">
            <strong>Sample data included</strong>
            <span>The template ships with example rows you can replace</span>
          </div>
        </div>
        <div className="feature-item">
          <span className="feature-icon">🤖</span>
          <div className="feature-text">
            <strong>AI-powered analysis</strong>
            <span>Our AI factors in external conditions to fine-tune recommendations</span>
          </div>
        </div>
      </div>

      <div className="columns-preview">
        <h3>Required columns</h3>
        <div className="columns-tags">
          {['Product Code', 'Product Name', 'Year', 'Opening Stock', 'Quantity Purchased', 'Closing Stock'].map(col => (
            <span key={col} className="tag">{col}</span>
          ))}
        </div>
      </div>

      <div className="btn-row" style={{ justifyContent: 'center', marginTop: '28px' }}>
        <button className="btn btn-primary btn-large" onClick={handleDownload}>
          <span className="btn-icon">⬇️</span>
          Download Excel Template
        </button>
        <button className="btn btn-secondary btn-large" onClick={onNext}>
          Skip — I already have the file →
        </button>
      </div>
    </div>
  )
}
