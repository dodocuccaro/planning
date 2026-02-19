# 📦 Retail Planning Tool

An AI-powered web application for retail purchasing planning. Upload historical stock and sales data, describe external market factors, and receive AI-generated purchase quantity recommendations per product.

## Features

- **Excel Template** — Download a pre-formatted template, fill in your historical data, re-upload
- **Automatic Sales Calculation** — `Sales = Opening Stock + Quantity Purchased − Closing Stock`
- **Trend Analysis** — Linear regression over historical years per product
- **AI Adjustment** — GPT-4o-mini analyses free-text external factors (weather, events, economy) and applies a demand multiplier
- **Visual Results** — Per-product charts (recharts), recommended order quantities, AI reasoning
- **Graceful Fallback** — Works fully without an OpenAI API key (uses neutral ×1.0 multiplier)

---

## Project Structure

```
planning/
├── backend/
│   ├── app.py            # Flask API (endpoints: /api/template, /api/upload, /api/analyze)
│   ├── planner.py        # Planning algorithm + OpenAI integration
│   ├── requirements.txt
│   └── .env.example      # Copy to .env and add your key
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── components/
│   │   │   ├── StepIndicator.jsx
│   │   │   ├── TemplateDownload.jsx
│   │   │   ├── FileUpload.jsx
│   │   │   ├── ExternalFactors.jsx
│   │   │   └── Results.jsx
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── .gitignore
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.9+
- Node.js 18+

### Backend

```bash
cd backend

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (optional — needed for AI features)
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...

# Run the server
python app.py
# Listening on http://localhost:5000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
# Open http://localhost:5173
```

> The Vite dev server proxies `/api` requests to `http://localhost:5000` automatically.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Optional | OpenAI API key for AI-powered demand adjustment. Without it the tool still works — it uses a neutral ×1.0 multiplier. |

---

## How to Use

### Step 1 — Download Template
Click **Download Excel Template**. Open the file in Excel or Google Sheets. The template contains sample data for three products across three years — replace it with your own.

**Required columns:**
| Column | Description |
|---|---|
| Product Code | Unique SKU / identifier |
| Product Name | Human-readable name |
| Year | 4-digit year (e.g. 2023) |
| Opening Stock | Units in stock at the start of the year |
| Quantity Purchased | Units ordered/purchased that year |
| Closing Stock | Units remaining at year end |

### Step 2 — Upload Data
Drag and drop (or click to browse) your filled-in `.xlsx` file. A preview table confirms the parsed data.

### Step 3 — External Factors
Describe any external conditions that may affect demand, e.g.:
- *"Heavy snowfall expected in Roccaraso — ski season up 30%"*
- *"New resort opening nearby, increasing tourist footfall"*
- *"Mild winter forecast, reduced demand for winter gear"*

You can also leave the field blank to rely solely on historical trends.

### Step 4 — Results
View per-product recommendations:
- 📊 Historical sales bar chart
- 📦 Recommended purchase quantity
- 📈 Trend percentage (year-over-year)
- 🤖 AI reasoning and adjustment multiplier

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/template` | Download the Excel template |
| `POST` | `/api/upload` | Upload Excel file (`multipart/form-data`, field `file`) |
| `POST` | `/api/analyze` | Run analysis (`{"data": [...], "external_factors": "..."}`) |
| `GET` | `/api/health` | Health check |

---

## Algorithm

For each product:

1. **Sales** = Opening Stock + Quantity Purchased − Closing Stock
2. **Average sales** = mean of annual sales
3. **Trend** = linear regression slope over years, expressed as % of average
4. **AI multiplier** = GPT-4o-mini analysis of external factors text → JSON `{"adjustment_factor": N}`
5. **Recommended purchase** = `ceil(avg_sales × (1 + trend) × ai_factor × 1.1)`
   - The `× 1.1` is a built-in 10% safety buffer
