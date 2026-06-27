_COLORS = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2",
    "#59a14f", "#edc948", "#b07aa1", "#ff9da7",
    "#9c755f", "#bab0ac",
]


def build_clarification_response(intent: dict, meta: dict = None) -> dict:
    ctype    = intent.get("clarification_type")
    question = intent.get("clarification_question") or "Puoi essere più specifico?"

    payload = {
        "type":               "clarification",
        "text":               question,
        "clarification_type": ctype,
        "options":            [],
        "proposed_filter":    None,
        "hint":               None,
    }

    if ctype == "category_ambiguous":
        payload["options"]   = intent.get("candidate_categories") or []
        payload["allow_all"] = True

    elif ctype == "multi_turn_confirm":
        payload["proposed_filter"] = intent.get("proposed_filter")
        payload["options"]         = ["Sì, procedi", "No, riscrivo la query"]

    elif ctype == "no_category_planning":
        payload["hint"] = "Seleziona una categoria o scrivila tu:"
        if meta and meta.get("categories"):
            payload["options"] = meta["categories"]

    elif ctype is None and meta and meta.get("categories"):
        # Generic clarification — still offer categories as quick-pick
        payload["options"] = meta["categories"]

    elif ctype == "price_unparseable":
        payload["hint"] = "Specifica il range di prezzo come: 'fascia 20-50€' oppure 'sotto i 30€'."

    return payload


def build_report_response(query_result: dict) -> dict:
    rows    = query_result["rows"]
    groups  = query_result["groups"]
    years   = query_result["years"]
    filters = query_result["filters_applied"]

    if not rows:
        return {"type": "empty", "text": "Nessun dato trovato con i filtri specificati."}

    # recharts BarChart data: [{year: "2022", GroupA: 120, GroupB: 85}, ...]
    chart_data = []
    for yr in years:
        entry = {"year": str(yr)}
        for group in groups:
            match = [r for r in rows if r["label"] == group and r["year"] == yr]
            entry[group] = round(match[0]["sales"], 0) if match else 0
        chart_data.append(entry)

    bars = [
        {"key": g, "color": _COLORS[i % len(_COLORS)]}
        for i, g in enumerate(groups)
    ]

    # Table
    table_columns = ["Gruppo"] + [str(y) for y in years] + ["Totale", "Media/anno"]
    table_rows = []
    for group in groups:
        sales_by_year = {r["year"]: r["sales"] for r in rows if r["label"] == group}
        total = sum(sales_by_year.get(y, 0) for y in years)
        row = {"Gruppo": group}
        for yr in years:
            row[str(yr)] = round(sales_by_year.get(yr, 0), 0)
        row["Totale"]      = round(total, 0)
        row["Media/anno"]  = round(total / len(years), 0) if years else 0
        table_rows.append(row)

    groupby    = filters.get("groupby")
    cats       = filters.get("categories")
    sups       = filters.get("supplier_names")
    yr_range   = f"{years[0]}–{years[-1]}" if len(years) > 1 else str(years[0]) if years else "tutti gli anni"
    cat_text   = f" ({', '.join(cats)})" if cats else ""
    sup_text   = f" — brand: {', '.join(sups)}" if sups else ""
    group_text = f" per {groupby}" if groupby else ""
    total_sales = sum(r["sales"] for r in rows)

    text = (
        f"Vendite{cat_text}{sup_text}{group_text} — {yr_range}. "
        f"Totale: {round(total_sales):,} unità "
        f"su {len(groups)} {'gruppi' if len(groups) > 1 else 'prodotto'} "
        f"e {len(years)} {'anni' if len(years) > 1 else 'anno'}."
    )

    return {
        "type":  "report",
        "text":  text,
        "chart": {"type": "bar", "data": chart_data, "x_key": "year", "bars": bars},
        "table": {"columns": table_columns, "rows": table_rows},
        "follow_up_suggestions": _suggestions(filters, "report"),
    }


def build_planning_response(query_result: dict) -> dict:
    planning = query_result.get("planning_results")
    filters  = query_result["filters_applied"]

    if not planning or not planning.get("products"):
        return {
            "type": "empty",
            "text": "Non è stato possibile generare raccomandazioni con i dati disponibili.",
        }

    cards = [
        {
            "label":                p["product_name"],
            "status":               p.get("status", "stable"),
            "trend_pct":            p.get("trend_pct", 0),
            "avg_sales":            p.get("avg_sales", 0),
            "forecast_demand":      p.get("forecast_demand", 0),
            "safety_stock":         p.get("safety_stock", 0),
            "current_stock":        p.get("current_stock", 0),
            "effective_stock":      p.get("effective_stock", p.get("current_stock", 0)),
            "sell_through_rate":    p.get("sell_through_rate"),
            "recommended_purchase": p.get("recommended_purchase", 0),
            "adjustment_factor":    p.get("adjustment_factor", 1.0),
            "critical_ratio":       p.get("critical_ratio"),
            "service_level_pct":    p.get("service_level_pct"),
            "unit_cost":            p.get("unit_cost"),
            "unit_price":           p.get("unit_price"),
            "gross_margin_pct":     p.get("gross_margin_pct"),
            "revenue_potential":    p.get("revenue_potential"),
            "margin_value":         p.get("margin_value"),
            "methodology":          p.get("methodology", ""),
            "ai_reasoning":         p.get("ai_reasoning", ""),
            "years":                p.get("years", []),
            "historical_sales":     p.get("historical_sales", []),
        }
        for p in planning["products"]
    ]

    summary = planning.get("summary_text", "").strip()
    if summary:
        text = summary + "\n\nSe vuoi vedere i dati nel dettaglio puoi esportarli su Excel."
    else:
        cats        = filters.get("categories")
        sups        = filters.get("supplier_names")
        cat_text    = f" ({', '.join(cats)})" if cats else ""
        sup_text    = f" — brand: {', '.join(sups)}" if sups else ""
        total_units = sum(c["recommended_purchase"] for c in cards)
        n_label     = "articoli" if len(cards) != 1 else "articolo"
        text = (
            f"Pianificazione acquisti{cat_text}{sup_text}. "
            f"{len(cards)} {n_label} · {total_units:,} unità totali consigliate.\n\n"
            "Se vuoi vedere i dati nel dettaglio puoi esportarli su Excel."
        )

    return {
        "type":          "planning",
        "text":          text,
        "cards":         cards,
        "ai_adjustment": planning.get("ai_adjustment"),
        "follow_up_suggestions": _suggestions(filters, "planning"),
    }


def build_both_response(query_result: dict) -> dict:
    report   = build_report_response(query_result)
    planning = build_planning_response(query_result)

    return {
        "type":         "both",
        "text":         (report.get("text", "") + "\n\n" + planning.get("text", "")).strip(),
        "chart":        report.get("chart"),
        "table":        report.get("table"),
        "cards":        planning.get("cards"),
        "ai_adjustment": planning.get("ai_adjustment"),
        "follow_up_suggestions": planning.get("follow_up_suggestions", []),
    }


def _suggestions(filters: dict, intent_type: str) -> list:
    groupby = filters.get("groupby")
    suggestions = []
    if intent_type == "report":
        if groupby != "color":
            suggestions.append("Vuoi vedere gli stessi dati per colore?")
        if groupby != "size":
            suggestions.append("Vuoi raggruppare per taglia?")
        suggestions.append("Vuoi una pianificazione acquisti basata su questi dati?")
        return suggestions[:2]
    elif intent_type == "planning":
        suggestions.append("Vuoi vedere i dati storici su cui si basa questa pianificazione?")
    return suggestions[:2]
