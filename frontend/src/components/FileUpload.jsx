import { useState, useRef, useCallback } from 'react'
import readXlsxFile from 'read-excel-file'

const PREVIEW_LIMIT = 8

// Required fixed columns in the wide-format template
const REQUIRED_FIXED = ['Product Code', 'Product Name', 'Current Stock']

// Regex to detect year sub-columns: "Opening Stock 2022", "Qty Purchased 2023", etc.
const YEAR_COL_RE = /^(Opening Stock|Qty Purchased|Closing Stock) (\d{4})$/

// ── Demo data (new wide format) ───────────────────────────────────────────────

const DEMO_DATA = [
  {
    product_code: 'SKI-JKT-001', product_name: 'Sci Jacket Pro',
    category: 'Abbigliamento', sales_channel: 'Main Store',
    currency: 'EUR', unit_of_measure: 'PZ', unit_cost: 85.00,
    current_stock: 42,
    history: [
      { year: 2022, opening_stock: 50,  qty_purchased: 300, closing_stock: 40 },
      { year: 2023, opening_stock: 40,  qty_purchased: 320, closing_stock: 35 },
      { year: 2024, opening_stock: 35,  qty_purchased: 350, closing_stock: 30 },
    ],
  },
  {
    product_code: 'SKI-JKT-001', product_name: 'Sci Jacket Pro',
    category: 'Abbigliamento', sales_channel: 'Online',
    currency: 'EUR', unit_of_measure: 'PZ', unit_cost: 85.00,
    current_stock: 18,
    history: [
      { year: 2022, opening_stock: 10, qty_purchased: 80,  closing_stock: 8 },
      { year: 2023, opening_stock: 8,  qty_purchased: 100, closing_stock: 6 },
      { year: 2024, opening_stock: 6,  qty_purchased: 130, closing_stock: 5 },
    ],
  },
  {
    product_code: 'SKI-BT-002', product_name: 'Alpine Ski Boots',
    category: 'Calzature', sales_channel: 'Main Store',
    currency: 'EUR', unit_of_measure: 'PZ', unit_cost: 120.00,
    current_stock: 55,
    history: [
      { year: 2022, opening_stock: 80, qty_purchased: 200, closing_stock: 60 },
      { year: 2023, opening_stock: 60, qty_purchased: 210, closing_stock: 50 },
      { year: 2024, opening_stock: 50, qty_purchased: 230, closing_stock: 45 },
    ],
  },
  {
    product_code: 'GLOVES-003', product_name: 'Thermal Gloves',
    category: 'Accessori', sales_channel: 'Main Store',
    currency: 'EUR', unit_of_measure: 'PZ', unit_cost: 22.50,
    current_stock: 95,
    history: [
      { year: 2022, opening_stock: 120, qty_purchased: 500, closing_stock: 80 },
      { year: 2023, opening_stock: 80,  qty_purchased: 540, closing_stock: 70 },
      { year: 2024, opening_stock: 70,  qty_purchased: 580, closing_stock: 60 },
    ],
  },
]

// ── Helpers ───────────────────────────────────────────────────────────────────

function calcLastYearSales(history) {
  if (!history || history.length === 0) return 0
  const last = [...history].sort((a, b) => b.year - a.year)[0]
  return Math.max(0, (last.opening_stock || 0) + (last.qty_purchased || 0) - (last.closing_stock || 0))
}

/**
 * Parse a wide-format Excel rows array (from readXlsxFile) into
 * the internal product-object list.
 */
function parseWideRows(rows) {
  if (!rows || rows.length < 2) throw new Error('The file contains no data rows.')

  const headers = rows[0].map(h => (h == null ? '' : String(h).trim()))

  // Check required fixed columns
  const missing = REQUIRED_FIXED.filter(c => !headers.includes(c))
  if (missing.length > 0)
    throw new Error(`Missing required columns: ${missing.join(', ')}`)

  // Detect years
  const yearsSet = new Set()
  for (const h of headers) {
    const m = YEAR_COL_RE.exec(h)
    if (m) yearsSet.add(Number(m[2]))
  }
  const years = [...yearsSet].sort((a, b) => a - b)
  if (years.length < 3)
    throw new Error(
      `Only ${years.length} year(s) found (${years.join(', ')}). ` +
      'At least 3 complete year groups are required.'
    )

  // Validate all sub-columns exist for each year
  for (const yr of years) {
    const missing = ['Opening Stock', 'Qty Purchased', 'Closing Stock']
      .filter(s => !headers.includes(`${s} ${yr}`))
    if (missing.length > 0)
      throw new Error(`Year ${yr} is missing columns: ${missing.map(s => `"${s} ${yr}"`).join(', ')}`)
  }

  const idx = {}
  for (const col of headers) idx[col] = headers.indexOf(col)

  const products = []
  for (let i = 1; i < rows.length; i++) {
    const row = rows[i]
    if (row.every(c => c == null || c === '')) continue

    const code    = String(row[idx['Product Code']]  ?? '').trim()
    const name    = String(row[idx['Product Name']]  ?? '').trim()
    if (!code && !name) continue

    const history = years.map(yr => ({
      year:          yr,
      opening_stock: Number(row[idx[`Opening Stock ${yr}`]])  || 0,
      qty_purchased: Number(row[idx[`Qty Purchased ${yr}`]])  || 0,
      closing_stock: Number(row[idx[`Closing Stock ${yr}`]])  || 0,
    }))

    const entry = {
      product_code:  code,
      product_name:  name,
      current_stock: Number(row[idx['Current Stock']]) || 0,
      history,
    }

    const optionals = {
      'Category':        'category',
      'Supplier Code':   'supplier_code',
      'Supplier Name':   'supplier_name',
      'Sales Channel':   'sales_channel',
      'Currency':        'currency',
      'Unit of Measure': 'unit_of_measure',
      'Unit Cost':       'unit_cost',
    }
    for (const [col, key] of Object.entries(optionals)) {
      if (idx[col] != null) {
        const val = row[idx[col]]
        entry[key] = val == null ? '' : typeof val === 'number' ? val : String(val).trim()
      }
    }

    products.push(entry)
  }

  if (products.length === 0) throw new Error('The file contains no data rows.')
  return { products, years }
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function FileUpload({ onNext, onBack, onDataLoaded }) {
  const [dragOver,    setDragOver]    = useState(false)
  const [loading,     setLoading]     = useState(false)
  const [error,       setError]       = useState(null)
  const [parsedData,  setParsedData]  = useState(null)
  const [fileName,    setFileName]    = useState(null)
  const inputRef = useRef(null)

  const processProducts = useCallback((products, years, source) => {
    const productCodes = new Set(products.map(p => p.product_code))
    const channels     = new Set(products.map(p => p.sales_channel).filter(Boolean))
    const data = {
      products,
      product_count: productCodes.size,
      year_count:    years.length,
      years,
      has_channel:   channels.size > 0,
      channels:      [...channels],
      source,
    }
    setParsedData(data)
    onDataLoaded(products)
  }, [onDataLoaded])

  const uploadFile = useCallback(async (file) => {
    setError(null)
    setLoading(true)
    setParsedData(null)
    try {
      let rows
      try {
        rows = await readXlsxFile(file, { sheet: 'Planning Template' })
      } catch {
        rows = await readXlsxFile(file)
      }
      const { products, years } = parseWideRows(rows)
      processProducts(products, years, file.name)
      setFileName(file.name)
    } catch (err) {
      setError(err.message || 'Upload failed. Please check the file and try again.')
    } finally {
      setLoading(false)
    }
  }, [processProducts])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) uploadFile(file)
  }, [uploadFile])

  const handleFileChange = (e) => {
    const file = e.target.files[0]
    if (file) uploadFile(file)
  }

  const handleDemoData = useCallback(() => {
    setError(null)
    const years = [...new Set(DEMO_DATA.flatMap(p => p.history.map(h => h.year)))].sort()
    processProducts(DEMO_DATA, years, 'demo')
    setFileName('demo-data')
  }, [processProducts])

  // ── Preview table ───────────────────────────────────────────────────────────
  const previewRows  = parsedData?.products?.slice(0, PREVIEW_LIMIT) || []
  const hasMore      = (parsedData?.products?.length || 0) > PREVIEW_LIMIT
  const hasChannel   = parsedData?.has_channel

  return (
    <div className="card">
      <h2 className="card-title">Upload Your Data</h2>
      <p className="card-subtitle">
        Upload the filled-in Excel template. We'll parse it and show you a preview before analysis.
      </p>

      {/* Drop zone */}
      <div
        className={`drop-zone ${dragOver ? 'drag-over' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        aria-label="Upload Excel file"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls"
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />
        {loading ? (
          <>
            <div className="drop-icon">⏳</div>
            <div className="drop-title">Parsing file…</div>
          </>
        ) : (
          <>
            <div className="drop-icon">📤</div>
            <div className="drop-title">
              {dragOver ? 'Drop it here!' : 'Drag & drop your Excel file here'}
            </div>
            <div className="drop-subtitle">or click to browse</div>
            <div className="drop-hint">Accepts .xlsx and .xls files</div>
          </>
        )}
      </div>

      {/* Demo data shortcut */}
      {!parsedData && !loading && (
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <span style={{ color: 'var(--gray-500)', fontSize: '.85rem', marginRight: 8 }}>— or —</span>
          <button className="btn btn-secondary" type="button" onClick={handleDemoData}>
            🎯 Try with Demo Data
          </button>
        </div>
      )}

      {/* File accepted confirmation */}
      {fileName && !loading && !error && (
        <div className="file-accepted">
          <span>✅</span>
          <span>
            {parsedData?.source === 'demo'
              ? <>Demo data loaded — <strong>{parsedData.product_count}</strong> products, <strong>{parsedData.year_count}</strong> years</>
              : <><strong>{fileName}</strong> — {parsedData?.products?.length} rows, {parsedData?.product_count} products, {parsedData?.year_count} years</>
            }
          </span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="alert alert-error" style={{ marginTop: 16 }}>
          <span className="alert-icon">⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {/* Preview table */}
      {previewRows.length > 0 && (
        <div className="preview-section">
          <div className="preview-header">
            <h3>Data Preview</h3>
            <span className="badge">
              {parsedData.products.length} rows · {parsedData.product_count} products · {parsedData.year_count} years
              {parsedData.has_channel ? ` · ${parsedData.channels.length} channels` : ''}
            </span>
          </div>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Product Code</th>
                  <th>Product Name</th>
                  {hasChannel && <th>Channel</th>}
                  <th>Current Stock</th>
                  <th>Last Year Sales</th>
                  <th>Years of History</th>
                </tr>
              </thead>
              <tbody>
                {previewRows.map((p, i) => (
                  <tr key={i}>
                    <td>{p.product_code}</td>
                    <td>{p.product_name}</td>
                    {hasChannel && <td>{p.sales_channel || '—'}</td>}
                    <td>{p.current_stock.toLocaleString()}</td>
                    <td>{calcLastYearSales(p.history).toLocaleString()}</td>
                    <td>{p.history.length}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {hasMore && (
              <div className="table-footer">
                Showing first {PREVIEW_LIMIT} of {parsedData.products.length} rows
              </div>
            )}
          </div>
        </div>
      )}

      <div className="btn-row">
        <button className="btn btn-secondary" onClick={onBack}>← Back</button>
        <button
          className="btn btn-primary"
          onClick={onNext}
          disabled={!parsedData || loading}
        >
          Continue →
        </button>
      </div>
    </div>
  )
}
