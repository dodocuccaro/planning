import os
import json
import math
import statistics
import numpy as np
from statistics import NormalDist
from openai import OpenAI

# Default critical ratio when margin data is unavailable.
# CR = Cu/(Cu+Co) = gross_margin_pct/100 under zero-salvage assumption.
DEFAULT_CRITICAL_RATIO = 0.60


def _linear_regression_slope(y_values):
    n = len(y_values)
    if n < 2:
        return 0.0
    x = list(range(n))
    x_mean = sum(x) / n
    y_mean = sum(y_values) / n
    numerator   = sum((x[i] - x_mean) * (y_values[i] - y_mean) for i in range(n))
    denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
    return 0.0 if denominator == 0 else numerator / denominator


def _get_ai_adjustment(external_factors: str, products_summary: list) -> dict:
    """
    Call OpenAI to get a demand adjustment factor based on external factors.
    Falls back gracefully if no API key is configured.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key == "your_key_here":
        return {
            "adjustment_factor": 1.0,
            "channel_adjustments": {},
            "reasoning": (
                "No OpenAI API key configured. Using neutral adjustment factor of 1.0. "
                "Set OPENAI_API_KEY in backend/.env to enable AI-powered analysis."
            ),
            "relevant_data_found": False,
        }

    client = OpenAI(api_key=api_key)

    products_text_parts = []
    for p in products_summary:
        years = p["years"]
        sales = p["sales_list"]
        year_lines = []
        for i, (yr, s) in enumerate(zip(years, sales)):
            if i == 0:
                year_lines.append(f"{yr}: {s:.0f} units")
            else:
                prev = sales[i - 1]
                pct  = ((s - prev) / prev * 100) if prev > 0 else 0.0
                year_lines.append(f"{yr}: {s:.0f} units ({pct:+.1f}% YoY)")
        channel_info = f", channel: {p['channel']}" if p.get("channel") else ""
        products_text_parts.append(
            f"- {p['product_name']} (code: {p['product_code']}{channel_info})\n"
            f"  Sales by year: {', '.join(year_lines)}\n"
            f"  Overall trend: {p['trend_pct']:+.1f}%/yr, avg: {p['avg_sales']:.0f} units/yr"
        )
    products_text = "\n".join(products_text_parts)

    channels = sorted({p["channel"] for p in products_summary if p.get("channel")})
    multi_channel = len(channels) > 1

    channel_instruction = ""
    if multi_channel:
        ch_list = ", ".join(f'"{c}"' for c in channels)
        channel_instruction = (
            f'\n  - channel_adjustments: an object mapping each sales channel ({ch_list}) '
            'to its own numeric multiplier. Use global adjustment_factor as fallback for '
            'any channel not listed.'
        )

    system_prompt = (
        "You are an expert retail purchasing analyst. "
        "A user will describe external factors that may affect demand for a set of retail products. "
        "You are also provided with year-by-year historical sales data for each product (and sales channel).\n\n"
        "Your job:\n"
        "1. Examine the historical data and identify years where sales deviated significantly from trend "
        "(large YoY spikes or drops). Consider whether those anomalies might correlate with the external "
        "factors described.\n"
        "2. Use this evidence to estimate how the described external conditions for the UPCOMING "
        "year should adjust the demand forecast.\n"
        "3. Return a single JSON object with:\n"
        "  - adjustment_factor: a numeric multiplier (1.2 = +20% demand, 0.8 = -20%). "
        "Use 1.0 if the factors are neutral or unrelated.\n"
        "  - reasoning: a concise explanation (3-5 sentences) citing specific years/data.\n"
        "  - relevant_data_found: true if external factors are clearly relevant to these products."
        f"{channel_instruction}\n\n"
        "Respond ONLY with a valid JSON object, no markdown, no extra text."
    )

    user_message = (
        f"Products and historical data:\n{products_text}\n\n"
        f"External factors described by the user:\n\"{external_factors}\"\n\n"
        "Please provide your demand adjustment assessment as a JSON object."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.3,
            max_tokens=400,
        )
        raw    = response.choices[0].message.content.strip()
        result = json.loads(raw)

        factor = float(result.get("adjustment_factor", 1.0))
        factor = max(0.1, min(5.0, factor))

        raw_ca            = result.get("channel_adjustments", {})
        channel_adjustments = {}
        if isinstance(raw_ca, dict):
            for ch, f in raw_ca.items():
                try:
                    channel_adjustments[str(ch)] = max(0.1, min(5.0, float(f)))
                except (TypeError, ValueError):
                    pass

        return {
            "adjustment_factor":  factor,
            "channel_adjustments": channel_adjustments,
            "reasoning":           str(result.get("reasoning", "")),
            "relevant_data_found": bool(result.get("relevant_data_found", True)),
        }
    except json.JSONDecodeError:
        return {
            "adjustment_factor": 1.0, "channel_adjustments": {},
            "reasoning": "AI returned an unexpected response format. Using neutral adjustment factor.",
            "relevant_data_found": False,
        }
    except Exception as exc:
        return {
            "adjustment_factor": 1.0, "channel_adjustments": {},
            "reasoning": f"AI analysis unavailable ({type(exc).__name__}). Using neutral adjustment factor of 1.0.",
            "relevant_data_found": False,
        }


def _summarize_plan(result_products: list, external_factors: str) -> str:
    """
    Generate a narrative summary of planning results highlighting the most
    important cases. Falls back to a deterministic summary when no API key.
    """
    to_buy  = [p for p in result_products if p.get("recommended_purchase", 0) > 0]
    to_skip = [p for p in result_products if p.get("recommended_purchase", 0) == 0]

    def _deterministic() -> str:
        sentences = []
        growing = sorted(
            [p for p in to_buy if p.get("status") == "growing"],
            key=lambda x: x.get("trend_pct", 0), reverse=True,
        )
        if growing:
            top = growing[0]
            sentences.append(
                f"{top['product_name']} guida la crescita ({top['trend_pct']:+.0f}%/anno), "
                f"ordine consigliato: {top['recommended_purchase']:,} pz."
            )
            others = [p["product_name"] for p in growing[1:3]]
            if others:
                sentences.append(f"In crescita anche: {', '.join(others)}.")
        declining = [p for p in to_buy if p.get("status") == "declining"]
        if declining:
            names = ", ".join(p["product_name"] for p in declining[:3])
            sentences.append(f"Modelli in calo da ridurre: {names}.")
        if to_skip:
            names = ", ".join(p["product_name"] for p in to_skip[:3])
            suffix = f" (e altri {len(to_skip) - 3})" if len(to_skip) > 3 else ""
            sentences.append(f"Da non riordinare: {names}{suffix}.")
        if not sentences:
            total = sum(p.get("recommended_purchase", 0) for p in to_buy)
            sentences.append(
                f"Pianificazione per {len(to_buy)} articoli — {total:,} unità totali."
            )
        return " ".join(sentences)

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key == "your_key_here":
        return _deterministic()

    client = OpenAI(api_key=api_key)

    lines = []
    for p in result_products:
        rec = p.get("recommended_purchase", 0)
        lines.append(
            f"- {p['product_name']}: trend {p.get('trend_pct', 0):+.1f}%/anno, "
            f"previsione {p.get('forecast_demand', 0):.0f} pz, ordine {rec} pz"
            + (f", stato: {p.get('status')}" if p.get("status") else "")
        )

    ext_text = (
        external_factors
        if external_factors and external_factors.strip() not in ("", "No external factors provided.")
        else "Nessun fattore esterno specificato."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Sei un buyer esperto di moda retail. "
                        "Scrivi un riassunto sintetico (4-6 frasi) in italiano dei risultati di pianificazione acquisti, "
                        "evidenziando: articoli in forte crescita da privilegiare, articoli in calo da ridurre, "
                        "articoli da non riordinare. Tono diretto e professionale, nessun elenco puntato — solo testo fluente. "
                        "Non includere frasi sull'export o sull'Excel."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Fattori esterni: {ext_text}\n\nArticoli:\n" + "\n".join(lines)
                    ),
                },
            ],
            temperature=0.4,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return _deterministic()


def analyze(data: list, external_factors: str) -> dict:
    """
    Main planning function.

    Parameters
    ----------
    data : list of product dicts, each with:
        product_code, product_name, current_stock,
        history: [{"year": int, "opening_stock": float,
                   "qty_purchased": float, "closing_stock": float}, ...]
        optional: sales_channel, category, currency, unit_of_measure, unit_cost

    external_factors : str

    Returns
    -------
    dict with keys: products, ai_adjustment, external_factors
    """
    products_summary = []

    for item in data:
        code              = str(item["product_code"])
        channel           = str(item.get("sales_channel") or "").strip()
        current_stock     = float(item.get("current_stock") or 0)
        unit_cost         = item.get("unit_cost")
        unit_price        = item.get("unit_price")
        gross_margin_pct  = item.get("gross_margin_pct")

        history = sorted(item.get("history", []), key=lambda r: int(r["year"]))

        sales_list   = []
        ordered_list = []
        years_list   = []
        for r in history:
            opening   = float(r.get("opening_stock",  0) or 0)
            purchased = float(r.get("qty_purchased",   0) or 0)
            closing   = float(r.get("closing_stock",   0) or 0)
            sales     = max(0.0, opening + purchased - closing)
            sales_list.append(sales)
            years_list.append(int(r["year"]))
            ordered_list.append(float(r.get("qty_ordered", 0) or 0))

        if not sales_list:
            continue

        # Sell-through rate
        str_pairs = [(s, o) for s, o in zip(sales_list, ordered_list) if o > 0]
        sell_through_rate = min(sum(s/o for s,o in str_pairs)/len(str_pairs), 1.0) if str_pairs else None

        last_year_sales = sales_list[-1]
        avg_sales       = sum(sales_list) / len(sales_list)
        slope           = _linear_regression_slope(sales_list)
        trend_fraction  = (slope / avg_sales) if avg_sales > 0 else 0.0
        trend_pct       = trend_fraction * 100.0

        # Residuals from the regression line — used for safety stock.
        # Using total stdev would inflate safety stock for trending products.
        n_yrs = len(sales_list)
        if n_yrs >= 2:
            x_mean_r  = (n_yrs - 1) / 2.0
            intercept_r = avg_sales - slope * x_mean_r
            residuals = [sales_list[i] - (intercept_r + i * slope) for i in range(n_yrs)]
            residual_std = statistics.stdev(residuals)
        else:
            residual_std = 0.0

        # Estimate residual stock from ordered-sold when no explicit stock data exists
        if current_stock == 0 and any(o > 0 for o in ordered_list):
            total_ordered = sum(ordered_list)
            total_sold    = sum(sales_list)
            estimated_residual = max(0.0, total_ordered - total_sold)
            current_stock = estimated_residual

        # Discontinuation detection: how many consecutive recent years have 0 sales
        zero_tail = 0
        for s in reversed(sales_list):
            if s == 0:
                zero_tail += 1
            else:
                break

        products_summary.append({
            "product_code":       code,
            "product_name":       str(item["product_name"]),
            "channel":            channel,
            "current_stock":      current_stock,
            "sell_through_rate":  sell_through_rate,
            "last_year_sales":    last_year_sales,
            "last_year_ordered":  ordered_list[-1] if ordered_list else 0.0,
            "avg_sales":          avg_sales,
            "slope":              slope,
            "trend_pct":          trend_pct,
            "trend_fraction":     trend_fraction,
            "residual_std":       residual_std,
            "sales_list":         sales_list,
            "years":              years_list,
            "unit_cost":          unit_cost,
            "unit_price":         unit_price,
            "zero_tail":          zero_tail,
            "gross_margin_pct":   gross_margin_pct,
        })

    # Planning base = products that were actually PURCHASED (qty_ordered > 0) in the
    # most recent season. A product sold in A25 from leftover A24 stock was not
    # re-ordered in A25, so it has no place in the A26 plan.
    if products_summary:
        max_year = max(ps["years"][-1] for ps in products_summary if ps["years"])
        products_summary = [
            ps for ps in products_summary
            if ps["years"] and ps["years"][-1] == max_year and ps["last_year_ordered"] > 0
        ]

    ai_result         = _get_ai_adjustment(external_factors, products_summary)
    global_factor     = ai_result["adjustment_factor"]
    channel_adjustments = ai_result.get("channel_adjustments", {})

    # Compute average gross margin across all products (for relative comparison)
    margins = [ps["gross_margin_pct"] for ps in products_summary if ps.get("gross_margin_pct") is not None]
    avg_margin = sum(margins) / len(margins) if margins else None

    result_products = []
    for ps in products_summary:
        avg               = ps["avg_sales"]
        last_yr_sales     = ps["last_year_sales"]
        slope             = ps["slope"]
        trend_fraction    = ps["trend_fraction"]
        residual_std      = ps["residual_std"]
        adjustment_factor = channel_adjustments.get(ps["channel"], global_factor)
        current_stock     = ps["current_stock"]
        sell_through_rate = ps["sell_through_rate"]
        gross_margin_pct  = ps.get("gross_margin_pct")
        unit_cost         = ps.get("unit_cost")
        unit_price        = ps.get("unit_price")
        zero_tail         = ps.get("zero_tail", 0)
        sales_list        = ps["sales_list"]
        name              = ps["product_name"]

        # ── Discontinuation & low-volume guard ───────────────────────────────
        # If no sales in last 1+ years → discontinued, do not reorder
        is_discontinued = zero_tail >= 1
        # Chronically low volume with negative trend → not worth stocking
        is_low_volume_declining = avg < 5 and trend_fraction < -0.05

        if is_discontinued or is_low_volume_declining:
            if is_discontinued:
                reason = (
                    f"Nessuna vendita registrata nell'ultima stagione nonostante la presenza a catalogo. "
                    f"Sconsiglio il riordino."
                )
            else:
                reason = (
                    f"Volumi storici troppo bassi (media {avg:.1f} pz/anno) con trend negativo ({ps['trend_pct']:+.1f}%/anno). "
                    f"Non genera volumi sufficienti per giustificare un ordine."
                )
            entry = {
                "product_code":         ps["product_code"],
                "product_name":         name,
                "years":                ps["years"],
                "historical_sales":     [round(s, 1) for s in sales_list],
                "last_year_sales":      round(ps["last_year_sales"], 0),
                "avg_sales":            round(avg, 1),
                "current_stock":        round(current_stock, 0),
                "effective_stock":      round(current_stock, 0),
                "sell_through_rate":    None,
                "trend_pct":            round(ps["trend_pct"], 1),
                "adjustment_factor":    1.0,
                "margin_multiplier":    1.0,
                "forecast_demand":      0,
                "safety_stock":         0,
                "target_stock":         0,
                "recommended_purchase": 0,
                "unit_cost":            unit_cost,
                "unit_price":           unit_price,
                "gross_margin_pct":     gross_margin_pct,
                "revenue_potential":    None,
                "margin_value":         None,
                "status":               "discontinued" if is_discontinued else "low_volume",
                "methodology":          reason,
                "ai_reasoning":         None,
            }
            if ps["channel"]:
                entry["sales_channel"] = ps["channel"]
            result_products.append(entry)
            continue

        # ── Normal planning path — Newsvendor model ──────────────────────────
        #
        # The newsvendor model finds the optimal order quantity for a single-season
        # product by balancing two costs:
        #   Cu = underage cost  = margin per unit not sold to a customer (lost profit)
        #   Co = overage cost   = cost of a unit bought but not sold (sunk cost)
        #
        # Optimal stock-up-to level: T* = F^-1(CR) where demand F ~ N(μ, σ)
        # Critical ratio: CR = Cu/(Cu+Co) = gross_margin%
        #   CR > 0.5 → high margin → stock above the mean forecast (can afford leftover)
        #   CR < 0.5 → thin margin → stock below the mean forecast (stockout cheaper than surplus)
        #   CR = 0.5 → margin = cost → order exactly the mean forecast

        # Demand forecast: linear extrapolation from last observed year
        forecast_demand = max(0.0, (last_yr_sales + slope) * adjustment_factor)

        # Effective usable existing stock (discounted by sell-through rate)
        effective_stock = (current_stock * sell_through_rate
                           if sell_through_rate is not None and current_stock > 0
                           else current_stock)

        # Critical ratio and implied z-score
        cr = min(0.95, max(0.10, gross_margin_pct / 100.0)) if gross_margin_pct is not None else DEFAULT_CRITICAL_RATIO
        z_cr = NormalDist().inv_cdf(cr)

        # Target stock at the CR-th percentile of demand
        target_stock = max(0.0, forecast_demand + z_cr * residual_std)
        recommended_purchase = max(0, math.ceil(target_stock - effective_stock))

        service_level_pct = round(cr * 100)
        # safety_stock equivalent for display: the z*sigma buffer
        safety_stock = z_cr * residual_std

        revenue_potential = round(recommended_purchase * unit_price, 2) if unit_price else None
        margin_value      = round(recommended_purchase * (unit_price - unit_cost), 2) if (unit_price and unit_cost) else None

        # ── Insight-driven methodology (synthesis, not raw data) ─────────────
        first_yr, last_yr = ps["years"][0], ps["years"][-1]
        first_s,  last_s  = sales_list[0], sales_list[-1]

        if trend_fraction > 0.10:
            trend_insight = (
                f"Le vendite sono in forte crescita (+{ps['trend_pct']:.0f}%/anno): "
                f"da {first_s:.0f} pz nel {first_yr} a {last_s:.0f} pz nel {last_yr}. "
                f"Brand da privilegiare negli acquisti."
            )
            status = "growing"
        elif trend_fraction > 0.02:
            trend_insight = (
                f"Crescita moderata (+{ps['trend_pct']:.0f}%/anno) negli ultimi {len(sales_list)} anni. "
                f"Domanda stabile e in aumento — buon segnale per il riordino."
            )
            status = "growing"
        elif trend_fraction > -0.05:
            trend_insight = (
                f"Domanda stabile attorno a {avg:.0f} pz/anno negli ultimi {len(sales_list)} anni. "
                f"Andamento prevedibile, pianificazione conservativa."
            )
            status = "stable"
        elif trend_fraction > -0.20:
            trend_insight = (
                f"Vendite in calo ({ps['trend_pct']:.0f}%/anno): "
                f"da {first_s:.0f} pz nel {first_yr} a {last_s:.0f} pz nel {last_yr}. "
                f"Ridurre il budget rispetto agli anni precedenti."
            )
            status = "declining"
        else:
            trend_insight = (
                f"Calo accelerato ({ps['trend_pct']:.0f}%/anno) — "
                f"le vendite si sono quasi azzerate rispetto al {first_yr}. "
                f"Valutare se mantenere il brand nel assortimento."
            )
            status = "declining"

        parts = [trend_insight]

        # Newsvendor margin insight
        if gross_margin_pct is not None:
            if cr > 0.62:
                parts.append(
                    f"Margine {gross_margin_pct:.0f}%: il modello punta al {service_level_pct}° percentile di domanda "
                    f"— con questo margine conviene avere stock in eccesso piuttosto che perdere vendite."
                )
            elif cr < 0.48:
                parts.append(
                    f"Margine {gross_margin_pct:.0f}%: target al {service_level_pct}° percentile "
                    f"— margine ridotto, meglio accettare qualche stockout che rischiare invenduto."
                )
            else:
                parts.append(
                    f"Margine {gross_margin_pct:.0f}%: costo invenduto e costo mancata vendita sostanzialmente bilanciati "
                    f"— ordine allineato alla previsione media."
                )

        if current_stock > 0 and sell_through_rate is not None:
            unsold = current_stock - effective_stock
            if unsold > 0:
                parts.append(
                    f"Stock residuo: {current_stock:.0f} pz in magazzino, di cui ~{effective_stock:.0f} previsti vendibili."
                )

        parts.append(
            f"Previsione domanda: {forecast_demand:.0f} pz | Stock target ({service_level_pct}° pct): "
            f"{target_stock:.0f} pz → Da ordinare: {recommended_purchase} pz."
        )
        if revenue_potential and margin_value is not None:
            parts.append(f"Potenziale ricavo: {revenue_potential:,.0f}€ | margine atteso: {margin_value:,.0f}€.")

        methodology = " ".join(parts)

        entry = {
            "product_code":         ps["product_code"],
            "product_name":         ps["product_name"],
            "years":                ps["years"],
            "historical_sales":     [round(s, 1) for s in ps["sales_list"]],
            "last_year_sales":      round(ps["last_year_sales"], 0),
            "avg_sales":            round(avg, 1),
            "current_stock":        round(current_stock, 0),
            "effective_stock":      round(effective_stock, 0),
            "sell_through_rate":    round(sell_through_rate, 3) if sell_through_rate is not None else None,
            "trend_pct":            round(ps["trend_pct"], 1),
            "adjustment_factor":    round(adjustment_factor, 3),
            "critical_ratio":       round(cr, 3),
            "service_level_pct":    service_level_pct,
            "forecast_demand":      round(forecast_demand, 0),
            "safety_stock":         round(safety_stock, 1),
            "target_stock":         round(target_stock, 0),
            "recommended_purchase": recommended_purchase,
            "unit_cost":            unit_cost,
            "unit_price":           unit_price,
            "gross_margin_pct":     gross_margin_pct,
            "revenue_potential":    revenue_potential,
            "margin_value":         margin_value,
            "status":               status,
            "methodology":          methodology,
            "ai_reasoning":         ai_result["reasoning"] if ai_result.get("relevant_data_found") else None,
        }
        if ps["channel"]:
            entry["sales_channel"] = ps["channel"]
        result_products.append(entry)

    summary_text = _summarize_plan(result_products, external_factors)

    return {
        "products":        result_products,
        "ai_adjustment":   ai_result,
        "external_factors": external_factors,
        "summary_text":    summary_text,
    }
