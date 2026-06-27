import planner as planner_module


def execute_query(intent: dict, adapter) -> dict:
    """
    Execute a resolved (non-clarification) query intent against a DataAdapter.

    Returns:
    {
        "rows":             [{"label": str, "year": int, "sales": float}],
        "planning_results": dict | None,
        "filters_applied":  {...},
        "groups":           [str],
        "years":            [int],
    }
    """
    pf              = intent.get("product_filter", {})
    categories      = pf.get("categories") or None
    price_min       = pf.get("price_min")
    price_max       = pf.get("price_max")
    supplier_names  = pf.get("supplier_names") or None
    years           = intent.get("years") or None
    groupby         = intent.get("groupby")
    intent_type     = intent.get("intent", "report")
    rec_filter      = intent.get("recommendation_filter", "all")
    external_factors = intent.get("external_factors") or "No external factors provided."

    rows = adapter.query(
        categories=categories,
        price_min=price_min,
        price_max=price_max,
        years=years,
        groupby=groupby,
        supplier_names=supplier_names,
    )

    groups        = sorted({r["label"] for r in rows})
    years_in_data = sorted({r["year"] for r in rows})

    planning_results = None
    if intent_type in ("planning", "both") and rows:
        planning_units = adapter.get_planning_units(
            categories=categories,
            price_min=price_min,
            price_max=price_max,
            years=years,
            groupby=groupby,
            supplier_names=supplier_names,
        )
        if planning_units:
            planning_results = planner_module.analyze(planning_units, external_factors)

            # Post-filter planning products by recommendation polarity.
            # Default "all" also strips discontinued products — they're shown
            # only when the user explicitly asks for "non devo comprare" (skip).
            prods = planning_results.get("products", [])
            if rec_filter == "skip":
                prods = [p for p in prods if p.get("recommended_purchase", 0) == 0]
            else:
                # "buy" or "all" — only show products actually worth ordering
                prods = [p for p in prods if p.get("recommended_purchase", 0) > 0]
            planning_results = {**planning_results, "products": prods}

    return {
        "rows": rows,
        "planning_results": planning_results,
        "filters_applied": {
            "categories":     categories,
            "supplier_names": supplier_names,
            "price_min":      price_min,
            "price_max":      price_max,
            "years":          years_in_data,
            "groupby":        groupby,
        },
        "groups": groups,
        "years":  years_in_data,
    }
