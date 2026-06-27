/**
 * Client-side port of the Python planning algorithm (backend/planner.py).
 * Accepts the new wide-format product structure with a history array.
 * Runs entirely in the browser — no backend required.
 */

// z-score for target service level (1.28 = 90%, 1.65 = 95%)
const RETAIL_SERVICE_LEVEL_Z = 1.28

function sampleStdDev(values) {
  if (values.length < 2) return 0
  const mean = values.reduce((a, b) => a + b, 0) / values.length
  const variance = values.reduce((acc, v) => acc + (v - mean) ** 2, 0) / (values.length - 1)
  return Math.sqrt(variance)
}

function linearRegressionSlope(yValues) {
  const n = yValues.length
  if (n < 2) return 0
  const xMean = (n - 1) / 2
  const yMean = yValues.reduce((a, b) => a + b, 0) / n
  const num = yValues.reduce((acc, y, i) => acc + (i - xMean) * (y - yMean), 0)
  const den = yValues.reduce((acc, _, i) => acc + (i - xMean) ** 2, 0)
  return den === 0 ? 0 : num / den
}

/**
 * Analyse product data and return purchase recommendations (offline mode).
 *
 * @param {Array<{
 *   product_code: string,
 *   product_name: string,
 *   current_stock: number,
 *   sales_channel?: string,
 *   history: Array<{year: number, opening_stock: number, qty_purchased: number, closing_stock: number}>
 * }>} data
 * @param {string} externalFactors
 * @returns {{ products: Array, ai_adjustment: object, external_factors: string }}
 */
export function analyze(data, externalFactors) {
  const aiResult = {
    adjustment_factor: 1.0,
    channel_adjustments: {},
    reasoning:
      'Running in static/offline mode. AI adjustment is unavailable without a backend. ' +
      'Using a neutral ×1.0 multiplier; recommendations are based solely on historical trends.',
    relevant_data_found: false,
  }

  const resultProducts = []

  for (const item of data) {
    const channel      = String(item.sales_channel || '').trim()
    const currentStock = Number(item.current_stock) || 0

    const history = [...(item.history || [])].sort((a, b) => a.year - b.year)

    const salesList = history.map(r => {
      const opening   = Number(r.opening_stock)  || 0
      const purchased = Number(r.qty_purchased)   || 0
      const closing   = Number(r.closing_stock)   || 0
      return Math.max(0, opening + purchased - closing)
    })

    if (salesList.length === 0) continue

    const years          = history.map(r => r.year)
    const lastYearSales  = salesList[salesList.length - 1]
    const avgSales       = salesList.reduce((a, b) => a + b, 0) / salesList.length
    const slope          = linearRegressionSlope(salesList)
    const trendFraction  = avgSales > 0 ? slope / avgSales : 0

    const adjustmentFactor = (aiResult.channel_adjustments || {})[channel] ?? aiResult.adjustment_factor

    // Base forecast: trend-adjusted mean × AI multiplier
    const forecastDemand = avgSales * (1 + trendFraction) * adjustmentFactor

    // Retail safety stock based on demand variability (CV × z-score)
    const stdDev      = sampleStdDev(salesList)
    const cv          = avgSales > 0 ? stdDev / avgSales : 0
    const safetyStock = avgSales * cv * RETAIL_SERVICE_LEVEL_Z

    // Target = what we want on hand at season start
    const targetStock         = forecastDemand + safetyStock
    const recommendedPurchase = Math.max(0, Math.ceil(targetStock - currentStock))

    const entry = {
      product_code:         String(item.product_code),
      product_name:         String(item.product_name),
      years,
      historical_sales:     salesList.map(s => Math.round(s * 10) / 10),
      last_year_sales:      Math.round(lastYearSales),
      avg_sales:            Math.round(avgSales * 10) / 10,
      current_stock:        currentStock,
      trend_pct:            Math.round(trendFraction * 1000) / 10,
      adjustment_factor:    adjustmentFactor,
      forecast_demand:      Math.round(forecastDemand),
      safety_stock:         Math.round(safetyStock),
      target_stock:         Math.round(targetStock),
      recommended_purchase: recommendedPurchase,
      ai_reasoning:         aiResult.reasoning,
    }
    if (channel) entry.sales_channel = channel

    resultProducts.push(entry)
  }

  return {
    products:        resultProducts,
    ai_adjustment:   aiResult,
    external_factors: externalFactors,
  }
}
