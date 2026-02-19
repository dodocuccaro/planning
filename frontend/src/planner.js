/**
 * Client-side port of the Python planning algorithm (backend/planner.py).
 * Runs entirely in the browser — no backend required.
 */

function linearRegressionSlope(yValues) {
  const n = yValues.length
  if (n < 2) return 0
  const x = yValues.map((_, i) => i)
  const xMean = x.reduce((a, b) => a + b, 0) / n
  const yMean = yValues.reduce((a, b) => a + b, 0) / n
  const num = x.reduce((acc, xi, i) => acc + (xi - xMean) * (yValues[i] - yMean), 0)
  const den = x.reduce((acc, xi) => acc + (xi - xMean) ** 2, 0)
  return den === 0 ? 0 : num / den
}

/**
 * Analyse uploaded rows and return purchase recommendations.
 *
 * @param {Array<{product_code,product_name,year,opening_stock,quantity_purchased,closing_stock}>} data
 * @param {string} externalFactors
 * @returns {{ products: Array, ai_adjustment: object, external_factors: string }}
 */
export function analyze(data, externalFactors) {
  // Group rows by product code
  const productMap = {}
  for (const row of data) {
    const code = String(row.product_code)
    if (!productMap[code]) {
      productMap[code] = { product_code: code, product_name: String(row.product_name), rows: [] }
    }
    productMap[code].rows.push(row)
  }

  // Sort each product's rows by year
  for (const code of Object.keys(productMap)) {
    productMap[code].rows.sort((a, b) => Number(a.year) - Number(b.year))
  }

  // Compute statistics per product
  const productsSummary = []
  for (const code of Object.keys(productMap)) {
    const prod = productMap[code]
    const salesList = prod.rows.map(r => {
      const opening = Number(r.opening_stock) || 0
      const purchased = Number(r.quantity_purchased) || 0
      const closing = Number(r.closing_stock) || 0
      return Math.max(0, opening + purchased - closing)
    })
    const avgSales = salesList.reduce((a, b) => a + b, 0) / salesList.length
    const slope = linearRegressionSlope(salesList)
    const trendFraction = avgSales > 0 ? slope / avgSales : 0
    const trendPct = trendFraction * 100

    productsSummary.push({
      product_code: code,
      product_name: prod.product_name,
      avg_sales: avgSales,
      trend_pct: trendPct,
      trend_fraction: trendFraction,
      sales_list: salesList,
      years: prod.rows.map(r => Number(r.year)),
    })
  }

  // No AI backend available on GitHub Pages — use neutral 1.0 multiplier
  const aiResult = {
    adjustment_factor: 1.0,
    reasoning:
      'Running in static/offline mode. AI adjustment is unavailable without a backend. ' +
      'Using a neutral ×1.0 multiplier; recommendations are based solely on historical trends.',
    relevant_data_found: false,
  }
  const adjustmentFactor = aiResult.adjustment_factor

  // Build final recommendations
  const resultProducts = productsSummary.map(ps => {
    const rawRec = ps.avg_sales * (1 + ps.trend_fraction) * adjustmentFactor * 1.1
    const recommendedPurchase = Math.ceil(Math.max(0, rawRec))
    return {
      product_code: ps.product_code,
      product_name: ps.product_name,
      years: ps.years,
      historical_sales: ps.sales_list.map(s => Math.round(s * 10) / 10),
      avg_sales: Math.round(ps.avg_sales * 10) / 10,
      trend_pct: Math.round(ps.trend_pct * 10) / 10,
      adjustment_factor: adjustmentFactor,
      recommended_purchase: recommendedPurchase,
      ai_reasoning: aiResult.reasoning,
    }
  })

  return {
    products: resultProducts,
    ai_adjustment: aiResult,
    external_factors: externalFactors,
  }
}
