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
├── render.yaml           # Render Blueprint (deploy backend in one click after merging to main)
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

| Variable | Where | Required | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Backend (Render) | Optional | OpenAI API key for AI-powered demand adjustment. Without it the tool still works — it uses a neutral ×1.0 multiplier. |
| `VITE_BACKEND_URL` | GitHub repository variable | Optional | Full URL of the deployed backend (e.g. `https://planning-backend.onrender.com`). When set, the frontend sends analysis requests to the backend so GPT-4o-mini can process them. Without it the frontend runs in offline mode. |

---

## Deploying the Backend (Render.com — free tier)

The Flask backend needs to be running somewhere so the frontend can call it for AI analysis.
Follow the steps below to deploy it to Render for free.

> **Note:** If you got a "render.yaml not found on main branch" error, that is because `render.yaml`
> is part of this PR and is not on `main` yet. Use the **manual setup** instructions below — they
> work immediately without needing to merge first.

### Option A — Manual setup (recommended, works right now)

1. **Sign up at [render.com](https://render.com)** (free account is enough).
2. From the Render dashboard click **New → Web Service**.
3. Connect this GitHub repository and choose the branch you want to deploy from.
4. Fill in the service settings:
   | Field | Value |
   |---|---|
   | **Name** | `planning-backend` (or any name you like) |
   | **Root Directory** | `backend` |
   | **Runtime** | `Python 3` |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `gunicorn app:app` |
5. Under **Environment Variables** add:
   - `OPENAI_API_KEY` = your OpenAI key (starts with `sk-...`)
6. Click **Create Web Service**. Render will build and deploy the backend.
7. Note the service URL shown at the top of the Render dashboard, e.g. `https://planning-backend.onrender.com`.

### Option B — Blueprint (after this PR is merged into main)

Once this PR is merged, you can also use Render's one-click Blueprint:

1. From the Render dashboard click **New → Blueprint** and connect this GitHub repository.
   Render will detect `render.yaml` on `main` and create the `planning-backend` web service automatically.
2. After the first deploy, go to the service's **Environment** tab and add `OPENAI_API_KEY`.
3. Note the service URL.

---

### Connecting the frontend (same for both options)

After the backend is deployed:

4. In your GitHub repository go to **Settings → Secrets and variables → Actions → Variables** (not Secrets).
5. Create a repository variable:
   - Name: `VITE_BACKEND_URL`
   - Value: the Render service URL from step 7 above (e.g. `https://planning-backend.onrender.com`)
6. Re-run the **Deploy to GitHub Pages** workflow (or push any commit to `main`).

The frontend will now call the backend for AI analysis. The ✅ **AI analysis active** banner will appear on the External Factors step when the connection is working.

> **Note:** Render's free tier spins down services after 15 minutes of inactivity. The first request after a period of inactivity may take ~30 seconds while the service starts up. This is normal.

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
