import os
import json
import math
import numpy as np
from openai import OpenAI

def _linear_regression_slope(y_values):
    """Return the slope of a simple linear regression over evenly spaced x."""
    n = len(y_values)
    if n < 2:
        return 0.0
    x = list(range(n))
    x_mean = sum(x) / n
    y_mean = sum(y_values) / n
    numerator = sum((x[i] - x_mean) * (y_values[i] - y_mean) for i in range(n))
    denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _get_ai_adjustment(external_factors: str, products_summary: list) -> dict:
    """
    Call OpenAI to get an adjustment factor based on external factors.

    Returns a dict with:
      adjustment_factor        – global fallback multiplier
      channel_adjustments      – optional {channel: factor} mapping
      reasoning                – explanation text
      relevant_data_found      – bool
    Falls back gracefully if no API key is set.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key == "your_key_here":
        return {
            "adjustment_factor": 1.0,
            "channel_adjustments": {},
            "reasoning": "No OpenAI API key configured. Using neutral adjustment factor of 1.0. "
                         "Set OPENAI_API_KEY in backend/.env to enable AI-powered analysis.",
            "relevant_data_found": False,
        }

    client = OpenAI(api_key=api_key)

    # Build detailed per-year, per-channel product text
    products_text_parts = []
    for p in products_summary:
        years = p["years"]
        sales = p["sales_list"]

        # Year-over-year lines
        year_lines = []
        for i, (yr, s) in enumerate(zip(years, sales)):
            if i == 0:
                year_lines.append(f"{yr}: {s:.0f} units")
            else:
                prev = sales[i - 1]
                pct = ((s - prev) / prev * 100) if prev > 0 else 0.0
                year_lines.append(f"{yr}: {s:.0f} units ({pct:+.1f}% YoY)")

        channel_info = f", channel: {p['channel']}" if p.get("channel") else ""
        products_text_parts.append(
            f"- {p['product_name']} (code: {p['product_code']}{channel_info})\n"
            f"  Sales by year: {', '.join(year_lines)}\n"
            f"  Overall trend: {p['trend_pct']:+.1f}%/yr, avg: {p['avg_sales']:.0f} units/yr"
        )

    products_text = "\n".join(products_text_parts)

    # Detect whether multiple channels are present
    channels = sorted({p["channel"] for p in products_summary if p.get("channel")})
    multi_channel = len(channels) > 1

    channel_instruction = ""
    if multi_channel:
        ch_list = ", ".join(f'"{c}"' for c in channels)
        channel_instruction = (
            f'\n  - channel_adjustments: an object mapping each sales channel ({ch_list}) '
            'to its own numeric multiplier, reflecting how differently each channel is affected '
            'by the described factors. Use the global adjustment_factor as fallback for any '
            'channel not listed.'
        )

    system_prompt = (
        "You are an expert retail purchasing analyst. "
        "A user will describe external factors that may affect demand for a set of retail products. "
        "You are also provided with year-by-year historical sales data for each product (and sales channel).\n\n"
        "Your job:\n"
        "1. Examine the historical data and identify years where sales deviated significantly from the trend "
        "(large YoY spikes or drops). Consider whether those anomalies might correlate with the external "
        "factors described — for example, if a year of heavy snowfall coincides with a +20% sales spike, "
        "that is evidence the factor drives demand for these products.\n"
        "2. Use this historical evidence to estimate how the described external conditions for the UPCOMING "
        "year should adjust the demand forecast.\n"
        "3. Return a single JSON object with:\n"
        "  - adjustment_factor: a numeric multiplier (e.g. 1.2 means +20% demand, 0.8 means -20%). "
        "Use 1.0 if the factors are neutral or unrelated.\n"
        "  - reasoning: a concise explanation (3-5 sentences) citing specific years/data that support "
        "your conclusion, and explaining which channels or products are most affected.\n"
        "  - relevant_data_found: true if the external factors are clearly relevant to these products, "
        "false otherwise."
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
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=400,
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        # Validate and clamp adjustment_factor to a sane range
        factor = float(result.get("adjustment_factor", 1.0))
        factor = max(0.1, min(5.0, factor))

        # Validate channel_adjustments if present
        raw_ca = result.get("channel_adjustments", {})
        channel_adjustments = {}
        if isinstance(raw_ca, dict):
            for ch, f in raw_ca.items():
                try:
                    channel_adjustments[str(ch)] = max(0.1, min(5.0, float(f)))
                except (TypeError, ValueError):
                    pass

        return {
            "adjustment_factor": factor,
            "channel_adjustments": channel_adjustments,
            "reasoning": str(result.get("reasoning", "")),
            "relevant_data_found": bool(result.get("relevant_data_found", True)),
        }
    except json.JSONDecodeError:
        return {
            "adjustment_factor": 1.0,
            "channel_adjustments": {},
            "reasoning": "AI returned an unexpected response format. Using neutral adjustment factor.",
            "relevant_data_found": False,
        }
    except Exception as exc:
        return {
            "adjustment_factor": 1.0,
            "channel_adjustments": {},
            "reasoning": f"AI analysis unavailable ({type(exc).__name__}). Using neutral adjustment factor of 1.0.",
            "relevant_data_found": False,
        }


def analyze(data: list, external_factors: str) -> dict:
    """
    Main planning function.

    Parameters
    ----------
    data : list of dicts with keys:
        product_code, product_name, year,
        opening_stock, quantity_purchased, closing_stock
        [optional] sales_channel
    external_factors : str
        Free-text description of external factors from the user.

    Returns
    -------
    dict with keys:
        products: list of per-product recommendation dicts
        ai_adjustment: the shared AI adjustment block
        external_factors: echoed back
    """
    # Group rows by product_code|||sales_channel (matches frontend convention)
    products: dict[str, dict] = {}
    for row in data:
        code = str(row["product_code"])
        channel = str(row.get("sales_channel") or "").strip()
        key = f"{code}|||{channel}"
        if key not in products:
            products[key] = {
                "product_code": code,
                "product_name": str(row["product_name"]),
                "channel": channel,
                "rows": [],
            }
        products[key]["rows"].append(row)

    # Sort each product's rows by year
    for key in products:
        products[key]["rows"].sort(key=lambda r: int(r["year"]))

    # Compute statistics per product+channel
    products_summary = []
    for key, prod in products.items():
        sales_list = []
        for r in prod["rows"]:
            opening = float(r.get("opening_stock", 0) or 0)
            purchased = float(r.get("quantity_purchased", 0) or 0)
            closing = float(r.get("closing_stock", 0) or 0)
            sales = opening + purchased - closing
            sales_list.append(max(0.0, sales))

        avg_sales = sum(sales_list) / len(sales_list) if sales_list else 0.0
        slope = _linear_regression_slope(sales_list)
        # Express trend as a fraction of average sales
        trend_fraction = (slope / avg_sales) if avg_sales > 0 else 0.0
        trend_pct = trend_fraction * 100.0

        products_summary.append({
            "product_code": prod["product_code"],
            "product_name": prod["product_name"],
            "channel": prod["channel"],
            "avg_sales": avg_sales,
            "trend_pct": trend_pct,
            "trend_fraction": trend_fraction,
            "sales_list": sales_list,
            "years": [int(r["year"]) for r in prod["rows"]],
        })

    # Get AI adjustment (single call for all products together)
    ai_result = _get_ai_adjustment(external_factors, products_summary)
    global_factor = ai_result["adjustment_factor"]
    channel_adjustments = ai_result.get("channel_adjustments", {})

    # Build final recommendations
    result_products = []
    for ps in products_summary:
        avg = ps["avg_sales"]
        trend_fraction = ps["trend_fraction"]
        # Use channel-specific factor if available, otherwise global
        adjustment_factor = channel_adjustments.get(ps["channel"], global_factor)
        # Recommended purchase with safety buffer of 10%
        raw_recommendation = avg * (1.0 + trend_fraction) * adjustment_factor * 1.1
        recommended_purchase = math.ceil(max(0.0, raw_recommendation))

        entry = {
            "product_code": ps["product_code"],
            "product_name": ps["product_name"],
            "years": ps["years"],
            "historical_sales": [round(s, 1) for s in ps["sales_list"]],
            "avg_sales": round(avg, 1),
            "trend_pct": round(ps["trend_pct"], 1),
            "adjustment_factor": adjustment_factor,
            "recommended_purchase": recommended_purchase,
            "ai_reasoning": ai_result["reasoning"],
        }
        if ps["channel"]:
            entry["sales_channel"] = ps["channel"]
        result_products.append(entry)

    return {
        "products": result_products,
        "ai_adjustment": ai_result,
        "external_factors": external_factors,
    }
