import { useState, useRef, useCallback } from 'react'
import readXlsxFile from 'read-excel-file'

const PREVIEW_LIMIT = 10

const REQUIRED_COLUMNS = [
  'Product Code',
  'Product Name',
  'Year',
  'Opening Stock',
  'Quantity Purchased',
  'Closing Stock',
]

export default function FileUpload({ onNext, onBack, onDataLoaded }) {
  const [dragOver, setDragOver]   = useState(false)
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)
  const [parsedData, setParsedData] = useState(null)
  const [fileName, setFileName]   = useState(null)
  const inputRef = useRef(null)

  const uploadFile = useCallback(async (file) => {
    setError(null)
    setLoading(true)
    setParsedData(null)

    try {
      // Try "Planning Template" sheet first, fall back to first sheet
      let rows
      try {
        rows = await readXlsxFile(file, { sheet: 'Planning Template' })
      } catch {
        rows = await readXlsxFile(file)
      }

      if (!rows || rows.length < 2) {
        throw new Error('The uploaded file contains no data rows.')
      }

      // First row = headers
      const headers = rows[0].map(h => (h == null ? '' : String(h).trim()))
      const missing = REQUIRED_COLUMNS.filter(col => !headers.includes(col))
      if (missing.length > 0) {
        throw new Error(`Missing required columns: ${missing.join(', ')}. Expected: ${REQUIRED_COLUMNS.join(', ')}`)
      }

      // Map column positions
      const idx = {}
      for (const col of REQUIRED_COLUMNS) idx[col] = headers.indexOf(col)

      // Parse data rows (skip header)
      const parsedRows = []
      for (let i = 1; i < rows.length; i++) {
        const row = rows[i]
        // Skip fully empty rows
        if (row.every(cell => cell == null || cell === '')) continue
        parsedRows.push({
          product_code: String(row[idx['Product Code']] ?? '').trim(),
          product_name: String(row[idx['Product Name']] ?? '').trim(),
          year: Number(row[idx['Year']]) || 0,
          opening_stock: Number(row[idx['Opening Stock']]) || 0,
          quantity_purchased: Number(row[idx['Quantity Purchased']]) || 0,
          closing_stock: Number(row[idx['Closing Stock']]) || 0,
        })
      }

      if (parsedRows.length === 0) {
        throw new Error('The uploaded file contains no data rows.')
      }

      const productCodes = [...new Set(parsedRows.map(r => r.product_code))]
      const data = {
        rows: parsedRows,
        row_count: parsedRows.length,
        product_count: productCodes.length,
        columns: REQUIRED_COLUMNS,
      }
      setParsedData(data)
      onDataLoaded(data.rows)
      setFileName(file.name)
    } catch (err) {
      setError(err.message || 'Upload failed. Please check the file and try again.')
    } finally {
      setLoading(false)
    }
  }, [onDataLoaded])

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

  const columns = ['product_code', 'product_name', 'year', 'opening_stock', 'quantity_purchased', 'closing_stock']
  const columnLabels = {
    product_code: 'Product Code',
    product_name: 'Product Name',
    year: 'Year',
    opening_stock: 'Opening Stock',
    quantity_purchased: 'Qty Purchased',
    closing_stock: 'Closing Stock',
  }

  const previewRows = parsedData?.rows?.slice(0, PREVIEW_LIMIT) || []
  const hasMore = (parsedData?.rows?.length || 0) > PREVIEW_LIMIT

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

      {/* File accepted confirmation */}
      {fileName && !loading && !error && (
        <div className="file-accepted">
          <span>✅</span>
          <span><strong>{fileName}</strong> — {parsedData?.row_count} rows, {parsedData?.product_count} products loaded</span>
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
            <span className="badge">{parsedData.row_count} rows · {parsedData.product_count} products</span>
          </div>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  {columns.map(col => (
                    <th key={col}>{columnLabels[col]}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {previewRows.map((row, i) => (
                  <tr key={i}>
                    {columns.map(col => (
                      <td key={col}>{row[col] ?? '—'}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {hasMore && (
              <div className="table-footer">
                Showing first {PREVIEW_LIMIT} of {parsedData.row_count} rows
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
