import json
import os
import re
from difflib import SequenceMatcher

from openai import OpenAI

SEMANTIC_SCHEMA = {
    "product_id":       ["product code", "codice", "sku", "codice articolo", "art", "cod art",
                         "codice prodotto", "item code", "item no", "item number", "codice art"],
    "product_name":     ["product name", "nome", "descrizione", "description", "articolo",
                         "nome articolo", "desc", "item name", "item description", "denominazione"],
    "color":            ["colore", "color", "colour", "col", "colorazione"],
    "size":             ["taglia", "size", "misura", "tg", "mis", "taglia/misura"],
    "category":         ["categoria", "category", "reparto", "department", "tipo", "gruppo",
                         "linea", "famiglia", "group", "family", "gruppo merce", "grp merce",
                         "gruppo articolo", "settore"],
    "supplier_name":    ["fornitore", "supplier", "vendor", "supplier name", "nome fornitore",
                         "ragione sociale fornitore", "rag soc fornitore"],
    "supplier_code":    ["codice fornitore", "supplier code", "vendor code", "cod fornitore",
                         "cod forn"],
    "sales_channel":    ["canale", "channel", "negozio", "store", "sales channel",
                         "canale vendita", "punto vendita", "pdv"],
    "unit_cost":        ["prezzo", "costo", "price", "cost", "unit cost", "costo unitario",
                         "prezzo acquisto", "costo medio", "prezzo costo", "pr acquisto"],
    "currency":         ["valuta", "currency", "moneta", "divisa"],
    "unit_of_measure":  ["unità misura", "uom", "unit of measure", "um", "unita misura", "udm"],
    "current_stock":    ["giacenza", "stock attuale", "current stock", "giacenza attuale",
                         "disponibilità", "disponibile", "falda", "scorta attuale", "giac att"],
    "opening_stock":    ["apertura", "opening", "inizio", "giacenza inizio", "opening stock",
                         "stock inizio", "giacenza iniziale", "scorta inizio", "giac inizio"],
    "qty_purchased":    ["acquistato", "purchased", "ordered", "qty purchased",
                         "quantità acquistata", "acquisti", "qta acquistata", "q.ta acquistata"],
    "closing_stock":    ["chiusura", "closing", "fine", "giacenza fine", "closing stock",
                         "stock fine", "giacenza finale", "scorta fine", "giac fine"],
    "qty_sold":         ["venduto", "sold", "qty sold", "vendite", "quantità venduta",
                         "qta venduta", "q.ta venduta", "pezzi venduti"],
}

YEAR_FIELDS = {"opening_stock", "qty_purchased", "closing_stock", "qty_sold"}
REQUIRED_FIELDS = {"product_id", "product_name"}
YEAR_PATTERN = re.compile(r"^(.+?)\s+(\d{4})$")

# For compound columns like "A22 — Stagione 2022/23 / Venduto (Normale)"
COMPOUND_COL_RE   = re.compile(r"^(.+?)\s*/\s*(.+)$")
YEAR_IN_SEASON_RE = re.compile(r"\b(\d{4})\b")
SHORT_SEASON_RE   = re.compile(r"\bA(\d{2})\b", re.IGNORECASE)


def flatten_multiheader(df):
    """
    Flatten a MultiIndex-column DataFrame (e.g. Atelier season exports).
    Returns (df_flattened, was_multiheader: bool).
    """
    import pandas as pd

    if not isinstance(df.columns, pd.MultiIndex):
        return df, False

    new_cols = []
    for col in df.columns:
        lvl0 = str(col[0]).strip()
        lvl1 = str(col[1]).strip().replace("\n", " ")
        if "Unnamed" in lvl0 and "Unnamed" in lvl1:
            new_cols.append(f"col_{len(new_cols)}")
        elif "Unnamed" in lvl0:
            new_cols.append(lvl1)
        elif "Unnamed" in lvl1:
            new_cols.append(lvl0)
        else:
            new_cols.append(f"{lvl0} / {lvl1}")

    df_flat = df.copy()
    df_flat.columns = new_cols
    return df_flat, True


def _parse_compound_col(col: str):
    """
    Parse compound column like 'A22 — Stagione 2022/23 / Venduto (Normale)'.
    Returns (year: int, field: str) or (None, None).
    """
    m = COMPOUND_COL_RE.match(col)
    if not m:
        return None, None

    season_part = m.group(1).strip()
    sub_part    = m.group(2).strip().lower().replace("\n", " ")

    year_match = YEAR_IN_SEASON_RE.search(season_part)
    if year_match:
        year = int(year_match.group(1))
    else:
        short_match = SHORT_SEASON_RE.search(season_part)
        year = (2000 + int(short_match.group(1))) if short_match else None

    if year is None:
        return None, None

    if any(w in sub_part for w in ["venduto", "sold", "vendite", "vend"]):
        return year, "qty_sold"
    if any(w in sub_part for w in ["acquis", "purchased"]):
        return year, "qty_purchased"
    if any(w in sub_part for w in ["esistenza", "closing", "chiusura", "fine"]):
        return year, "closing_stock"
    if any(w in sub_part for w in ["apertura", "opening", "inizio"]):
        return year, "opening_stock"

    return year, None


def _similarity(a: str, b: str) -> float:
    a, b = a.lower().strip(), b.lower().strip()
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.88
    return SequenceMatcher(None, a, b).ratio()


def _fuzzy_match(col_header: str):
    """Returns (semantic_field, confidence) for best match, or (None, score)."""
    col_norm = col_header.lower().strip()
    best_field, best_score = None, 0.0
    for field, synonyms in SEMANTIC_SCHEMA.items():
        for syn in synonyms:
            score = _similarity(col_norm, syn)
            if score > best_score:
                best_score = score
                best_field = field
    if best_score >= 0.6:
        return best_field, best_score
    return None, best_score


def map_columns(headers: list, sample_row: dict = None) -> dict:
    """
    Map Excel column headers to semantic fields.

    Returns:
    {
        "mapping":          {"Original Col": "semantic_field"},
        "confidence":       {"Original Col": 0.95},
        "year_groups":      {2022: {"opening_stock": "Col 2022", ...}},
        "unmapped":         ["Col X"],
        "missing_required": ["product_id"],
        "needs_confirmation": bool,
    }
    """
    mapping = {}
    confidence = {}
    year_groups = {}
    unmapped = []

    for col in headers:
        col = str(col).strip()

        # 1. Try compound format: "A22 — Stagione 2022/23 / Venduto (Normale)"
        yr, field = _parse_compound_col(col)
        if yr and field:
            year_groups.setdefault(yr, {})[field] = col
            mapping[col] = "year_data"
            confidence[col] = 0.95
            continue

        # 2. Try year-suffix format: "Venduto 2022"
        m = YEAR_PATTERN.match(col)
        if m:
            base, yr = m.group(1).strip(), int(m.group(2))
            field, conf = _fuzzy_match(base)
            if field in YEAR_FIELDS:
                year_groups.setdefault(yr, {})[field] = col
                mapping[col] = "year_data"
                confidence[col] = round(conf, 3)
                continue

        # 3. Standard field match
        field, conf = _fuzzy_match(col)
        if field and field not in YEAR_FIELDS:
            mapping[col] = field
            confidence[col] = round(conf, 3)
        else:
            unmapped.append(col)

    mapped_semantic = {v for v in mapping.values() if v != "year_data"}
    missing_required = [f for f in REQUIRED_FIELDS if f not in mapped_semantic]
    low_conf_cols = [c for c, cf in confidence.items() if cf < 0.75 and mapping.get(c) != "year_data"]

    if (missing_required or low_conf_cols) and sample_row is not None:
        ai_result = _ai_map_columns(headers, sample_row)
        if ai_result:
            for col, field in ai_result.get("mapping", {}).items():
                if col in [str(h).strip() for h in headers]:
                    mapping[col] = field
                    confidence[col] = float(ai_result.get("confidence", {}).get(col, 0.8))
            mapped_semantic = {v for v in mapping.values() if v != "year_data"}
            missing_required = [f for f in REQUIRED_FIELDS if f not in mapped_semantic]
            all_mapped = set(mapping.keys())
            unmapped = [str(h).strip() for h in headers if str(h).strip() not in all_mapped]

    needs_confirmation = bool(missing_required) or any(
        cf < 0.85 for col, cf in confidence.items() if mapping.get(col) != "year_data"
    )

    return {
        "mapping":           mapping,
        "confidence":        confidence,
        "year_groups":       year_groups,
        "unmapped":          unmapped,
        "missing_required":  missing_required,
        "needs_confirmation": needs_confirmation,
    }


def _ai_map_columns(headers: list, sample_row: dict) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key == "your_key_here":
        return {}
    client = OpenAI(api_key=api_key)
    schema_desc = "\n".join(
        f"- {k}: e.g. {', '.join(v[:3])}" for k, v in SEMANTIC_SCHEMA.items()
    )
    cols_text = "\n".join(
        f'  - "{h}": sample = {repr(sample_row.get(str(h).strip(), ""))}'
        for h in headers[:30]
    )
    prompt = (
        f"Map these Excel column headers to semantic fields for a retail planning tool.\n\n"
        f"Available semantic fields:\n{schema_desc}\n\n"
        f"Column headers with sample values:\n{cols_text}\n\n"
        f'Return JSON only: {{"mapping": {{"col_name": "field"}}, "confidence": {{"col_name": 0.0}}}}\n'
        f"Only include columns mappable with confidence >= 0.7. Skip year-suffixed columns."
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=600,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception:
        return {}


def build_products_from_mapping(df, mapping_result: dict):
    """
    Convert a DataFrame + mapping result into internal product dicts.
    Returns (products_list, error_str_or_None).
    """
    import pandas as pd

    mapping = mapping_result["mapping"]
    year_groups = mapping_result["year_groups"]

    if not year_groups:
        return None, "Nessuna colonna annuale trovata. Il file deve contenere dati per almeno 3 anni."

    if len(year_groups) < 3:
        return None, f"Trovati solo {len(year_groups)} anno/i di dati. Minimo richiesto: 3."

    rev = {v: k for k, v in mapping.items() if v != "year_data"}

    id_col   = rev.get("product_id")
    name_col = rev.get("product_name")
    cat_col  = rev.get("category")

    # Fallback: use category column as product identifier if product_id/name missing
    if (not id_col or id_col not in df.columns) and cat_col and cat_col in df.columns:
        id_col = cat_col
    if (not name_col or name_col not in df.columns) and cat_col and cat_col in df.columns:
        name_col = cat_col

    # If still missing, allow product_id == product_name
    if id_col and not name_col:
        name_col = id_col
    if name_col and not id_col:
        id_col = name_col

    if not id_col or id_col not in df.columns:
        return None, "Impossibile identificare la colonna codice prodotto. Assegnala manualmente."
    if not name_col or name_col not in df.columns:
        return None, "Impossibile identificare la colonna nome prodotto. Assegnala manualmente."

    df = df.dropna(subset=[id_col], how="all").copy()
    df[id_col]   = df[id_col].astype(str).str.strip()
    df[name_col] = df[name_col].astype(str).str.strip()

    # Exclude summary rows (TOTALE, TOTALI, TOTAL, etc.)
    total_mask = df[id_col].str.upper().str.strip().isin(["TOTALE", "TOTALI", "TOTAL", "TOT"])
    df = df[~total_mask].copy()

    optional_fields = [
        "category", "color", "size", "supplier_name", "supplier_code",
        "sales_channel", "unit_cost", "currency", "unit_of_measure", "current_stock",
    ]
    years_sorted = sorted(year_groups.keys())

    products = []
    for _, row in df.iterrows():
        history = []
        for yr in years_sorted:
            yg = year_groups[yr]
            if "qty_sold" in yg:
                sold = float(pd.to_numeric(row.get(yg["qty_sold"], 0), errors="coerce") or 0)
                # Keep closing_stock=0 so planner formula (opening+purchased-closing) = sold directly.
                # The Esistenza column is used only for current_stock derivation below.
                # Store real ordered qty separately for sell-through rate calculation.
                ordered_col = yg.get("qty_purchased", "")
                ordered = float(pd.to_numeric(row.get(ordered_col, 0), errors="coerce") or 0) if ordered_col else 0.0
                history.append({"year": yr, "opening_stock": 0, "qty_purchased": sold, "closing_stock": 0, "qty_ordered": ordered})
            else:
                op = float(pd.to_numeric(row.get(yg.get("opening_stock", ""), 0), errors="coerce") or 0)
                qp = float(pd.to_numeric(row.get(yg.get("qty_purchased", ""), 0), errors="coerce") or 0)
                cs = float(pd.to_numeric(row.get(yg.get("closing_stock", ""), 0), errors="coerce") or 0)
                history.append({"year": yr, "opening_stock": op, "qty_purchased": qp, "closing_stock": cs})

        entry = {
            "product_code":  row[id_col],
            "product_name":  row[name_col],
            "current_stock": 0.0,
            "history":       history,
        }

        # Derive current_stock from the closing_stock column of the most recent year.
        # Read directly from year_groups because when qty_sold is present we store
        # closing_stock=0 in history to keep the sales formula correct (0 + sold - 0 = sold).
        if years_sorted:
            last_yr = years_sorted[-1]
            cs_col = year_groups[last_yr].get("closing_stock", "")
            if cs_col and cs_col in df.columns:
                cs_val = float(pd.to_numeric(row.get(cs_col, 0), errors="coerce") or 0)
                if cs_val > 0:
                    entry["current_stock"] = cs_val

        for field in optional_fields:
            col = rev.get(field)
            if col and col in df.columns:
                val = row.get(col, "")
                if field in ("unit_cost", "current_stock"):
                    entry[field] = float(pd.to_numeric(val, errors="coerce") or 0)
                else:
                    entry[field] = "" if (val is None or (isinstance(val, float) and pd.isna(val))) else str(val).strip()

        products.append(entry)

    return products, None


# ── Multi-sheet report parser ─────────────────────────────────────────────────

_SHEET_SEASON_RE = re.compile(r'[Aa](\d{2})\b')


def is_multisheet_report(sheet_names: list) -> bool:
    """Return True if the workbook looks like a multi-sheet report (Acquistato/Venduto per stagione)."""
    if len(sheet_names) < 2:
        return False
    hits = sum(
        1 for s in sheet_names
        if re.search(r'acquist|vendut', s, re.IGNORECASE) and _SHEET_SEASON_RE.search(s)
    )
    return hits >= 2


def _parse_report_sheet(xl, sheet_name: str):
    """
    Read one report sheet.
    Returns (year: int, metric: 'qty_sold'|'qty_purchased', df) or (None, None, None).
    df has columns: product_code, brand, qty
    """
    import pandas as pd

    m = _SHEET_SEASON_RE.search(sheet_name)
    if not m:
        return None, None, None
    year = 2000 + int(m.group(1))

    sheet_lower = sheet_name.lower()
    if re.search(r'acquist', sheet_lower):
        metric = 'qty_purchased'
    elif re.search(r'vendut', sheet_lower):
        metric = 'qty_sold'
    else:
        return None, None, None

    df_raw = pd.read_excel(xl, sheet_name=sheet_name, header=None, dtype=str)

    # Find the row where the first non-empty cell IS exactly 'ModelloVariante'
    header_row = None
    for i, row in df_raw.iterrows():
        first_val = next((str(v).strip() for v in row if str(v).strip() not in ('', 'nan')), '')
        if first_val == 'ModelloVariante':
            header_row = i
            break
    if header_row is None:
        return None, None, None

    # Slice data rows, assign column names from header row
    headers = [str(v).strip() for v in df_raw.iloc[header_row]]
    df = df_raw.iloc[header_row + 1:].copy()
    df.columns = headers
    df = df.reset_index(drop=True)

    code_col  = headers[0]   # ModelloVariante
    brand_col = headers[1]   # Brand
    qty_col   = headers[2]   # Acquisito _Q / Venduto _Q
    price_col = headers[3] if len(headers) > 3 else None  # Acquisito _P / Venduto _P

    keep_cols = [code_col, brand_col, qty_col]
    if price_col:
        keep_cols.append(price_col)

    df = df[keep_cols].copy()
    df.columns = ['product_code', 'brand', 'qty'] + (['price_total'] if price_col else [])

    # Drop empty / total rows
    df['product_code'] = df['product_code'].astype(str).str.strip()
    df = df[df['product_code'].notna()]
    df = df[~df['product_code'].isin(['', 'nan'])]
    df = df[~df['product_code'].str.fullmatch(r'\d+')]   # pure-number = totals row

    df['qty'] = pd.to_numeric(df['qty'], errors='coerce').fillna(0.0)
    if 'price_total' in df.columns:
        df['price_total'] = pd.to_numeric(df['price_total'], errors='coerce').fillna(0.0)
    df['brand'] = df['brand'].astype(str).str.strip().replace('nan', '')

    return year, metric, df


def parse_multisheet_report(xl_bytes: bytes):
    """
    Parse a multi-sheet Excel report (one sheet per stagione/metrica).
    Returns (products_list, category_str, error_str_or_None).
    """
    import pandas as pd
    import io

    xl = pd.ExcelFile(io.BytesIO(xl_bytes))

    # Extract category from first sheet metadata (looks for 'Gruppo' label)
    category = None
    for sname in xl.sheet_names:
        df_meta = pd.read_excel(xl, sheet_name=sname, header=None, dtype=str, nrows=5)
        for i in range(len(df_meta)):
            row_vals = [str(v).strip() for v in df_meta.iloc[i]]
            try:
                gi = next(j for j, v in enumerate(row_vals) if v == 'Gruppo')
                cat_raw = row_vals[gi + 1].replace('\n', ' ').strip()
                if cat_raw and cat_raw != 'nan':
                    category = cat_raw
                    break
            except (StopIteration, IndexError):
                pass
        if category:
            break

    bought_by_year:       dict = {}  # year -> {code: qty}
    sold_by_year:         dict = {}  # year -> {code: qty}
    bought_value_by_year: dict = {}  # year -> {code: total_cost}
    sold_value_by_year:   dict = {}  # year -> {code: total_revenue}
    brands:               dict = {}  # code -> brand

    for sname in xl.sheet_names:
        year, metric, df = _parse_report_sheet(xl, sname)
        if df is None:
            continue
        is_bought = (metric == 'qty_purchased')
        qty_target   = bought_by_year   if is_bought else sold_by_year
        value_target = bought_value_by_year if is_bought else sold_value_by_year

        for _, row in df.iterrows():
            code  = row['product_code']
            qty   = float(row['qty'])
            brand = row['brand']
            if brand:
                brands[code] = brand
            qty_target.setdefault(year, {})[code] = qty
            if 'price_total' in df.columns:
                val = float(row.get('price_total', 0) or 0)
                value_target.setdefault(year, {})[code] = val

    all_years = sorted(set(list(bought_by_year) + list(sold_by_year)))
    if len(all_years) < 3:
        return None, category, f"Trovati solo {len(all_years)} anni di dati. Minimo richiesto: 3."

    # Union of all product codes that appear in sold data at least once
    all_codes = set()
    for d in sold_by_year.values():
        all_codes.update(d.keys())
    for d in bought_by_year.values():
        all_codes.update(d.keys())

    products = []
    for code in sorted(all_codes):
        brand = brands.get(code, '')
        history = []
        for yr in all_years:
            ordered  = bought_by_year.get(yr, {}).get(code, 0.0)
            sold     = sold_by_year.get(yr, {}).get(code, 0.0)
            history.append({
                "year":          yr,
                "opening_stock": 0.0,
                "qty_purchased": sold,     # planner: 0 + sold - 0 = sold ✓
                "closing_stock": 0.0,
                "qty_ordered":   ordered,
            })

        # Skip products with zero sales across all years
        if all(h["qty_purchased"] == 0 for h in history):
            continue

        # Compute weighted-average unit_cost and unit_price across years with data
        total_cost_val = sum(bought_value_by_year.get(yr, {}).get(code, 0.0) for yr in all_years)
        total_cost_qty = sum(bought_by_year.get(yr, {}).get(code, 0.0) for yr in all_years)
        total_rev_val  = sum(sold_value_by_year.get(yr, {}).get(code, 0.0) for yr in all_years)
        total_rev_qty  = sum(sold_by_year.get(yr, {}).get(code, 0.0) for yr in all_years)

        unit_cost  = round(total_cost_val / total_cost_qty, 2) if total_cost_qty > 0 else None
        unit_price = round(total_rev_val  / total_rev_qty,  2) if total_rev_qty  > 0 else None
        if unit_cost and unit_price and unit_price > 0:
            gross_margin_pct = round((unit_price - unit_cost) / unit_price * 100, 1)
        else:
            gross_margin_pct = None

        products.append({
            "product_code":     code,
            "product_name":     f"{brand} {code}".strip() if brand else code,
            "category":         category or "",
            "supplier_name":    brand,
            "current_stock":    0.0,
            "unit_cost":        unit_cost,
            "unit_price":       unit_price,
            "gross_margin_pct": gross_margin_pct,
            "history":          history,
        })

    if not products:
        return None, category, "Nessun prodotto con dati di vendita trovato nel file."

    return products, category, None
