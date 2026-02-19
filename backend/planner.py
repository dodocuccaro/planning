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
    Returns a dict with adjustment_factor, reasoning, relevant_data_found.
    Falls back gracefully if no API key is set.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key == "your_key_here":
        return {
            "adjustment_factor": 1.0,
            "reasoning": "No OpenAI API key configured. Using neutral adjustment factor of 1.0. "
                         "Set OPENAI_API_KEY in backend/.env to enable AI-powered analysis.",
            "relevant_data_found": False,
        }

    client = OpenAI(api_key=api_key)

    products_text = "\n".join(
        f"- {p['product_name']} (code: {p['product_code']}): avg annual sales {p['avg_sales']:.0f} units, "
        f"trend {p['trend_pct']:+.1f}%"
        for p in products_summary
    )

    system_prompt = (
        "You are an expert retail purchasing analyst. "
        "A user will describe external factors that may affect demand for a set of retail products. "
        "Your job is to assess these factors and return a single JSON object with:\n"
        "  - adjustment_factor: a numeric multiplier (e.g. 1.2 means +20% demand, 0.8 means -20%). "
        "    Use 1.0 if the factors are neutral or unrelated.\n"
        "  - reasoning: a concise explanation (2-4 sentences) of why you chose that factor.\n"
        "  - relevant_data_found: true if the external factors are clearly relevant to these products, false otherwise.\n\n"
        "Respond ONLY with a valid JSON object, no markdown, no extra text."
    )

    user_message = (
        f"Products being planned:\n{products_text}\n\n"
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
            max_tokens=300,
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        # Validate and clamp adjustment_factor to a sane range
        factor = float(result.get("adjustment_factor", 1.0))
        factor = max(0.1, min(5.0, factor))
        return {
            "adjustment_factor": factor,
            "reasoning": str(result.get("reasoning", "")),
            "relevant_data_found": bool(result.get("relevant_data_found", True)),
        }
    except json.JSONDecodeError:
        return {
            "adjustment_factor": 1.0,
            "reasoning": "AI returned an unexpected response format. Using neutral adjustment factor.",
            "relevant_data_found": False,
        }
    except Exception as exc:
        return {
            "adjustment_factor": 1.0,
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
    external_factors : str
        Free-text description of external factors from the user.

    Returns
    -------
    dict with keys:
        products: list of per-product recommendation dicts
        ai_adjustment: the shared AI adjustment block
        external_factors: echoed back
    """
    # Group rows by product
    products: dict[str, dict] = {}
    for row in data:
        code = str(row["product_code"])
        if code not in products:
            products[code] = {
                "product_code": code,
                "product_name": str(row["product_name"]),
                "rows": [],
            }
        products[code]["rows"].append(row)

    # Sort each product's rows by year
    for code in products:
        products[code]["rows"].sort(key=lambda r: int(r["year"]))

    # Compute statistics per product
    products_summary = []
    for code, prod in products.items():
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
            "product_code": code,
            "product_name": prod["product_name"],
            "avg_sales": avg_sales,
            "trend_pct": trend_pct,
            "trend_fraction": trend_fraction,
            "sales_list": sales_list,
            "years": [int(r["year"]) for r in prod["rows"]],
        })

    # Get AI adjustment (single call for all products together)
    ai_result = _get_ai_adjustment(external_factors, products_summary)
    adjustment_factor = ai_result["adjustment_factor"]

    # Build final recommendations
    result_products = []
    for ps in products_summary:
        avg = ps["avg_sales"]
        trend_fraction = ps["trend_fraction"]
        # Recommended purchase with safety buffer of 10%
        raw_recommendation = avg * (1.0 + trend_fraction) * adjustment_factor * 1.1
        recommended_purchase = math.ceil(max(0.0, raw_recommendation))

        result_products.append({
            "product_code": ps["product_code"],
            "product_name": ps["product_name"],
            "years": ps["years"],
            "historical_sales": [round(s, 1) for s in ps["sales_list"]],
            "avg_sales": round(avg, 1),
            "trend_pct": round(ps["trend_pct"], 1),
            "adjustment_factor": adjustment_factor,
            "recommended_purchase": recommended_purchase,
            "ai_reasoning": ai_result["reasoning"],
        })

    return {
        "products": result_products,
        "ai_adjustment": ai_result,
        "external_factors": external_factors,
    }
