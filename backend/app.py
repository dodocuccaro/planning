import io
import os
from datetime import datetime

import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from dotenv import load_dotenv

import planner

load_dotenv()

app = Flask(__name__)
CORS(app)

REQUIRED_COLUMNS = [
    "Product Code",
    "Product Name",
    "Year",
    "Opening Stock",
    "Quantity Purchased",
    "Closing Stock",
]

# Optional column included in the template but not required for upload
OPTIONAL_COLUMNS = ["Sales Channel"]

# All columns that appear in the template (required + optional)
TEMPLATE_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

SAMPLE_DATA = [
    # Product A — Ski Jacket (two channels)
    {"Product Code": "SKI-JKT-001", "Product Name": "Ski Jacket Pro", "Sales Channel": "Main Store", "Year": 2022, "Opening Stock": 50, "Quantity Purchased": 300, "Closing Stock": 40},
    {"Product Code": "SKI-JKT-001", "Product Name": "Ski Jacket Pro", "Sales Channel": "Main Store", "Year": 2023, "Opening Stock": 40, "Quantity Purchased": 320, "Closing Stock": 35},
    {"Product Code": "SKI-JKT-001", "Product Name": "Ski Jacket Pro", "Sales Channel": "Main Store", "Year": 2024, "Opening Stock": 35, "Quantity Purchased": 350, "Closing Stock": 30},
    {"Product Code": "SKI-JKT-001", "Product Name": "Ski Jacket Pro", "Sales Channel": "Online",     "Year": 2022, "Opening Stock": 10, "Quantity Purchased":  80, "Closing Stock":  8},
    {"Product Code": "SKI-JKT-001", "Product Name": "Ski Jacket Pro", "Sales Channel": "Online",     "Year": 2023, "Opening Stock":  8, "Quantity Purchased": 100, "Closing Stock":  6},
    {"Product Code": "SKI-JKT-001", "Product Name": "Ski Jacket Pro", "Sales Channel": "Online",     "Year": 2024, "Opening Stock":  6, "Quantity Purchased": 130, "Closing Stock":  5},
    # Product B — Ski Boots
    {"Product Code": "SKI-BT-002",  "Product Name": "Alpine Ski Boots", "Sales Channel": "Main Store", "Year": 2022, "Opening Stock": 80, "Quantity Purchased": 200, "Closing Stock": 60},
    {"Product Code": "SKI-BT-002",  "Product Name": "Alpine Ski Boots", "Sales Channel": "Main Store", "Year": 2023, "Opening Stock": 60, "Quantity Purchased": 210, "Closing Stock": 50},
    {"Product Code": "SKI-BT-002",  "Product Name": "Alpine Ski Boots", "Sales Channel": "Main Store", "Year": 2024, "Opening Stock": 50, "Quantity Purchased": 230, "Closing Stock": 45},
    # Product C — Thermal Gloves
    {"Product Code": "GLOVES-003",  "Product Name": "Thermal Gloves",   "Sales Channel": "Main Store", "Year": 2022, "Opening Stock": 120, "Quantity Purchased": 500, "Closing Stock": 80},
    {"Product Code": "GLOVES-003",  "Product Name": "Thermal Gloves",   "Sales Channel": "Main Store", "Year": 2023, "Opening Stock": 80,  "Quantity Purchased": 540, "Closing Stock": 70},
    {"Product Code": "GLOVES-003",  "Product Name": "Thermal Gloves",   "Sales Channel": "Main Store", "Year": 2024, "Opening Stock": 70,  "Quantity Purchased": 580, "Closing Stock": 60},
]


def _build_template_excel() -> bytes:
    """Generate and return the Excel template as bytes."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Planning Template"

    # Styles
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill("solid", fgColor="1E3A5F")
    example_fill = PatternFill("solid", fgColor="EBF3FB")
    center = Alignment(horizontal="center", vertical="center")
    thin = Side(style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    col_widths = [18, 22, 8, 16, 20, 16, 18]

    # Header row
    for col_idx, (col_name, width) in enumerate(zip(TEMPLATE_COLUMNS, col_widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = width

    ws.row_dimensions[1].height = 28

    # Sample data rows
    for row_idx, row_data in enumerate(SAMPLE_DATA, start=2):
        for col_idx, col_name in enumerate(TEMPLATE_COLUMNS, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=row_data.get(col_name, ""))
            cell.fill = example_fill
            cell.border = border
            cell.alignment = center

    # Instructions sheet
    ws_info = wb.create_sheet("Instructions")
    instructions = [
        ("Planning Tool — Excel Template Instructions", True),
        ("", False),
        ("1. Do NOT rename or remove any column headers in the 'Planning Template' sheet.", False),
        ("2. You may delete the example rows (rows 2 onwards) and enter your own data.", False),
        ("3. Each row represents ONE product for ONE year (and optionally one sales channel).", False),
        ("4. Required columns:", False),
        ("   • Product Code  — unique identifier (e.g. SKI-JKT-001)", False),
        ("   • Product Name  — human-readable name", False),
        ("   • Year          — 4-digit year (e.g. 2022)", False),
        ("   • Opening Stock — units in stock at the START of the year", False),
        ("   • Quantity Purchased — units purchased/ordered that year", False),
        ("   • Closing Stock — units remaining at the END of the year", False),
        ("5. Optional column:", False),
        ("   • Sales Channel — shop name or channel (e.g. 'Main Store', 'Online'). Leave blank if you only have one channel.", False),
        ("   When provided, the AI will produce separate recommendations per channel and analyse", False),
        ("   which external factors affect each channel most.", False),
        ("6. Sales are calculated automatically: Opening Stock + Quantity Purchased - Closing Stock", False),
        ("7. Include at least 2-3 years of data per product for better forecasts.", False),
    ]
    ws_info.column_dimensions["A"].width = 80
    for r_idx, (text, bold) in enumerate(instructions, start=1):
        cell = ws_info.cell(row=r_idx, column=1, value=text)
        if bold:
            cell.font = Font(bold=True, size=13)
        ws_info.row_dimensions[r_idx].height = 18

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


@app.route("/api/template", methods=["GET"])
def get_template():
    """Return the Excel planning template as a file download."""
    try:
        excel_bytes = _build_template_excel()
        buf = io.BytesIO(excel_bytes)
        buf.seek(0)
        filename = f"planning_template_{datetime.now().strftime('%Y%m%d')}.xlsx"
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        return jsonify({"error": f"Failed to generate template: {str(exc)}"}), 500


@app.route("/api/upload", methods=["POST"])
def upload_file():
    """
    Accept an Excel file upload and parse it.
    Returns JSON with the parsed rows and column preview.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file field in request. Expected field name: 'file'"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    filename_lower = file.filename.lower()
    if not (filename_lower.endswith(".xlsx") or filename_lower.endswith(".xls")):
        return jsonify({"error": "Only Excel files (.xlsx, .xls) are supported"}), 400

    try:
        contents = file.read()
        df = pd.read_excel(io.BytesIO(contents), sheet_name="Planning Template")
    except Exception:
        # Try reading first sheet if the named sheet is not found
        try:
            df = pd.read_excel(io.BytesIO(contents))
        except Exception as exc:
            return jsonify({
                "error": (
                    f"Could not read Excel file: {str(exc)}. "
                    "Make sure the file contains a sheet named 'Planning Template' "
                    "(as in the downloaded template)."
                )
            }), 422

    # Validate required columns (case-insensitive)
    df.columns = [str(c).strip() for c in df.columns]
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        return jsonify({
            "error": f"Missing required columns: {missing}. "
                     f"Expected: {REQUIRED_COLUMNS}"
        }), 422

    # Drop rows where all required fields are NaN
    df = df.dropna(subset=REQUIRED_COLUMNS, how="all")

    if df.empty:
        return jsonify({"error": "The uploaded file contains no data rows"}), 422

    # Coerce numeric columns
    for col in ["Year", "Opening Stock", "Quantity Purchased", "Closing Stock"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["Product Code"] = df["Product Code"].astype(str).str.strip()
    df["Product Name"] = df["Product Name"].astype(str).str.strip()

    # Build JSON-serialisable list
    rows = []
    has_channel = "Sales Channel" in df.columns
    if has_channel:
        df["Sales Channel"] = df["Sales Channel"].fillna("").astype(str).str.strip()
    for _, row in df.iterrows():
        entry = {
            "product_code": row["Product Code"],
            "product_name": row["Product Name"],
            "year": int(row["Year"]),
            "opening_stock": float(row["Opening Stock"]),
            "quantity_purchased": float(row["Quantity Purchased"]),
            "closing_stock": float(row["Closing Stock"]),
        }
        if has_channel:
            entry["sales_channel"] = row["Sales Channel"]
        rows.append(entry)

    return jsonify({
        "rows": rows,
        "row_count": len(rows),
        "product_count": df["Product Code"].nunique(),
        "columns": REQUIRED_COLUMNS + (["Sales Channel"] if has_channel else []),
    })


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    Accept parsed data + external factors text and return planning recommendations.
    Body: {"data": [...], "external_factors": "..."}
    """
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Request body must be JSON"}), 400

    data = body.get("data")
    external_factors = str(body.get("external_factors", "")).strip()

    if not data or not isinstance(data, list):
        return jsonify({"error": "'data' must be a non-empty list of row objects"}), 400

    if not external_factors:
        external_factors = "No external factors provided."

    try:
        results = planner.analyze(data, external_factors)
        return jsonify(results)
    except Exception as exc:
        return jsonify({"error": f"Analysis failed: {str(exc)}"}), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=5000, debug=debug)
