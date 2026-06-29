import json
import os

from openai import OpenAI


def parse_intent(message: str, history: list, available_categories: list,
                 available_attributes: list, available_years: list,
                 available_suppliers: list = None) -> dict:
    """
    Parse a natural language message into a structured query intent.

    Returns:
    {
        "intent": "report" | "planning" | "both",
        "product_filter": {"categories": [...], "supplier_names": [...],
                           "price_min": null, "price_max": null},
        "groupby": str | null,
        "years": [int] | null,
        "external_factors": str,
        "recommendation_filter": "all" | "buy" | "skip",
        "needs_clarification": bool,
        "clarification_question": str | null,
        "clarification_type": str | null,
        "proposed_filter": dict | null,
        "candidate_categories": list | null,
    }
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key == "your_key_here":
        return _fallback_intent(message, available_categories, available_suppliers)

    client = OpenAI(api_key=api_key)

    cats_json       = json.dumps(available_categories, ensure_ascii=False)
    attrs_text      = ", ".join(available_attributes) if available_attributes else "product"
    years_json      = json.dumps(available_years)
    suppliers_json  = json.dumps(available_suppliers or [], ensure_ascii=False)

    history_text = ""
    if history:
        last_turns = history[-4:]
        history_text = "\n".join(
            f"[{t['role'].upper()}]: {t['content']}"
            for t in last_turns
            if isinstance(t.get("content"), str)
        )

    system_prompt = f"""You are an intent parser for a retail planning assistant. Extract structured query parameters from user messages.

Available product categories (EXACT values — use only these): {cats_json}
Available grouping attributes: {attrs_text}
Available years in data: {years_json}
Available supplier/brand names (EXACT values — use only these): {suppliers_json}

RULES:
1. "categories" must contain ONLY exact values from the categories list above. Never invent or approximate categories.
2. "supplier_names" must contain ONLY exact values from the supplier list above. Never invent suppliers.
3. If a category keyword partially matches MULTIPLE available categories, set needs_clarification=true, clarification_type="category_ambiguous", candidate_categories=[matching ones].
4. If intent includes "planning" and categories is empty/null AND supplier_names is empty/null, set needs_clarification=true, clarification_type="no_category_planning".
5. If the message is a short follow-up (under 10 words, no product/category/brand mentioned) AND history exists with prior filters, propose inheriting those filters: needs_clarification=true, clarification_type="multi_turn_confirm", proposed_filter={{full proposed intent}}, clarification_question="Confermo: stai chiedendo [inherited context], raggruppato per [new groupby]. È corretto?".
6. Price ranges: parse strictly. "fascia 20-50€", "tra 20 e 50", "sotto i 30€", "sopra 100" → price_min/price_max as floats. If present but unparseable → needs_clarification=true, clarification_type="price_unparseable".
7. "years": extract from "ultimi N anni" (compute from available_years), "dal YYYY", "YYYY-YYYY", explicit years. null = all available.
8. "groupby": detect from "per colore", "per taglia", "per canale", "per fornitore", "per categoria", "per brand", "per marchio", "per marca". Map "brand"/"marchio"/"marca"/"fornitore" → "supplier_name".
9. "recommendation_filter": detect when user wants only products to STOP buying or avoid ("smettere di comprare", "smettere di ordinare", "non devo comprare", "non dovrei comprare", "non comprare più", "evitare", "tagliare", "eliminare", "interrompere", "non ordinare", "sconsigliati", "should not buy", "stop buying", "avoid") → "skip". When user wants only recommended products → "buy". Otherwise → "all".
10. Respond in the same language as the user (Italian or English).

INTENT TYPES:
- "report": user wants historical data, charts, summaries
- "planning": user wants purchase recommendations for next season
- "both": user wants data and recommendations

Return ONLY a valid JSON object:
{{
  "intent": "report",
  "product_filter": {{"categories": [], "supplier_names": [], "price_min": null, "price_max": null}},
  "groupby": null,
  "years": null,
  "external_factors": "",
  "recommendation_filter": "all",
  "needs_clarification": false,
  "clarification_question": null,
  "clarification_type": null,
  "proposed_filter": null,
  "candidate_categories": null
}}"""

    user_content = ""
    if history_text:
        user_content += f"Conversation so far:\n{history_text}\n\n"
    user_content += f'Current message: "{message}"'

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content},
            ],
            temperature=0.1,
            max_tokens=500,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        return _validate_intent(result, available_categories, available_years, message, available_suppliers)
    except json.JSONDecodeError:
        return _fallback_intent(message, available_categories, available_suppliers)
    except Exception:
        return _fallback_intent(message, available_categories, available_suppliers)


def _keyword_filter_categories(message: str, available_categories: list) -> list:
    """
    Return the subset of available_categories that best match the user message.

    Strategy (from most precise to broadest):
    1. ALL relevant keywords must appear in the category name → tightest match
    2. Fall back to ANY keyword if step 1 returns nothing
    3. Fall back to full list if nothing matches at all

    "Relevant" keywords are words (3+ chars, not stopwords) that actually
    appear in at least one category name — this drops words like "prossimo",
    "anno", "per" that are not product-related.
    """
    msg_lower = message.lower()
    stopwords = {"che", "con", "per", "del", "dei", "gli", "una", "uno", "sul",
                 "sui", "nel", "nei", "dal", "dai", "alla", "agli", "degli",
                 "delle", "vuoi", "vorrei", "dammi", "mostra", "fammi", "vedere",
                 "fare", "anni", "anno", "dati", "report", "lista", "tutti", "tutte",
                 "prossimo", "prossima", "stagione", "prossimi", "ultimi", "ultima",
                 "questo", "questa", "voglio", "quanto", "quanti",
                 "acquisto", "comprare", "ordinare", "pianificazione", "storico"}

    words = [w for w in msg_lower.split() if len(w) >= 3 and w not in stopwords]

    if not words:
        return available_categories

    cats_lower = [(cat, cat.lower()) for cat in available_categories]

    # Keep only words that actually appear in at least one category name
    relevant_words = [w for w in words if any(w in cl for _, cl in cats_lower)]

    if not relevant_words:
        # No word matches any category — return full list
        return available_categories

    # Step 1: ALL relevant words must appear in the category
    all_match = [cat for cat, cl in cats_lower if all(w in cl for w in relevant_words)]
    if all_match:
        return all_match

    # Step 2: ANY relevant word matches
    any_match = [cat for cat, cl in cats_lower if any(w in cl for w in relevant_words)]
    return any_match if any_match else available_categories


def _validate_intent(result: dict, available_categories: list, available_years: list,
                     message: str = "", available_suppliers: list = None) -> dict:
    """Enforce hard constraints on parsed intent."""
    pf = result.setdefault("product_filter", {})

    # Categories must be exact matches
    cats = pf.get("categories") or []
    pf["categories"] = [c for c in cats if c in available_categories]

    # supplier_names must be exact matches
    sups = pf.get("supplier_names") or []
    if available_suppliers:
        pf["supplier_names"] = [s for s in sups if s in available_suppliers]
    else:
        pf["supplier_names"] = []

    # If AI returned category_ambiguous clarification, apply keyword filter to candidates
    if result.get("clarification_type") == "category_ambiguous" and message:
        raw_candidates = result.get("candidate_categories") or available_categories
        filtered = _keyword_filter_categories(message, raw_candidates)
        result["candidate_categories"] = filtered
        if len(filtered) == 1:
            pf["categories"] = filtered
            result["needs_clarification"] = False
            result["clarification_type"] = None
            result["clarification_question"] = None
            result["candidate_categories"] = None

    # If no categories resolved but message has keywords, try to match
    if not pf["categories"] and not pf["supplier_names"] and message and available_categories:
        filtered = _keyword_filter_categories(message, available_categories)
        if len(filtered) == 1:
            pf["categories"] = filtered
        elif len(filtered) < len(available_categories):
            # Multiple keyword matches — ask only about those
            if result.get("needs_clarification") or result.get("intent") == "planning":
                result["needs_clarification"] = True
                result["clarification_type"] = "category_ambiguous"
                result["candidate_categories"] = filtered
                result["clarification_question"] = (
                    f"Hai detto «{message}»: intendi una di queste categorie?"
                )

    # Years must be valid
    years = result.get("years")
    if years:
        valid = [y for y in years if y in available_years]
        result["years"] = valid if valid else None

    # recommendation_filter must be valid
    rf = result.get("recommendation_filter", "all")
    if rf not in ("all", "buy", "skip"):
        rf = "all"
    result["recommendation_filter"] = rf

    # Ensure all required keys exist
    defaults = {
        "intent": "report",
        "groupby": None,
        "external_factors": "",
        "recommendation_filter": "all",
        "needs_clarification": False,
        "clarification_question": None,
        "clarification_type": None,
        "proposed_filter": None,
        "candidate_categories": None,
    }
    for k, v in defaults.items():
        result.setdefault(k, v)

    return result


_GROUPBY_KEYWORDS = {
    "brand":        "supplier_name",
    "brands":       "supplier_name",
    "marchio":      "supplier_name",
    "marchi":       "supplier_name",
    "marca":        "supplier_name",
    "fornitore":    "supplier_name",
    "fornitori":    "supplier_name",
    "supplier":     "supplier_name",
    "colore":       "color",
    "colori":       "color",
    "color":        "color",
    "taglia":       "size",
    "taglie":       "size",
    "size":         "size",
    "canale":       "sales_channel",
    "canali":       "sales_channel",
    "categoria":    "category",
    "categorie":    "category",
}


_GROUPBY_TRIGGERS = ("per ", "by ", "raggruppat", "divid", "suddivid", "separat")


def _extract_groupby(message: str):
    msg_lower = message.lower()
    for kw, field in _GROUPBY_KEYWORDS.items():
        idx = msg_lower.find(kw)
        if idx == -1:
            continue
        # Only treat as groupby when preceded by a grouping trigger word
        prefix = msg_lower[:idx]
        if any(t in prefix for t in _GROUPBY_TRIGGERS):
            return field
        # Also accept "per <kw>" directly adjacent
        if prefix.rstrip().endswith("per") or prefix.rstrip().endswith("by"):
            return field
    return None


_SKIP_WORDS = [
    "smettere di comprare", "smettere di ordinare", "smettere di acquistare",
    "non devo comprare", "non debba comprare", "non dovrei comprare",
    "non comprare più", "non ordinare più", "non acquistare più",
    "non ordinare", "non comprare", "non acquistare",
    "evitare", "sconsigliati", "sconsigliato", "da evitare",
    "tagliare", "eliminare", "interrompere", "sospendere", "discontinuare",
    "non rinnovare", "non riordinare",
    "should not buy", "stop buying", "avoid", "not buy", "skip",
]

_BUY_WORDS = [
    "devo comprare", "debba comprare", "dovrei comprare",
    "da comprare", "da ordinare", "raccomandati", "consigliati",
    "should buy", "recommended",
]


def _detect_recommendation_filter(message: str) -> str:
    msg_lower = message.lower()
    for phrase in _SKIP_WORDS:
        if phrase in msg_lower:
            return "skip"
    for phrase in _BUY_WORDS:
        if phrase in msg_lower:
            return "buy"
    return "all"


def _match_suppliers(message: str, available_suppliers: list) -> list:
    """Return suppliers whose name appears as a word in the message (case-insensitive)."""
    if not available_suppliers:
        return []
    msg_lower = message.lower()
    matched = []
    for s in available_suppliers:
        if s.lower() in msg_lower:
            matched.append(s)
    return matched


def _fallback_intent(message: str, available_categories: list = None,
                     available_suppliers: list = None) -> dict:
    """Minimal safe intent when AI is unavailable."""
    msg_lower = message.lower()
    planning_words = ["compro", "comprare", "acquisto", "ordinare", "order", "buy",
                      "pianificaz", "consiglio", "puntare", "investire", "scommettere",
                      "raccomand", "suggest", "consigli"]
    intent = "planning" if any(w in msg_lower for w in planning_words) else "report"
    groupby = _extract_groupby(message)
    recommendation_filter = _detect_recommendation_filter(message)

    # Detect brand names before category matching
    matched_suppliers = _match_suppliers(message, available_suppliers)

    cats = []
    ctype = None
    question = None
    candidate_categories = None

    # If supplier matched and planning intent, we can proceed without category
    needs_clarification = True

    if available_categories:
        filtered = _keyword_filter_categories(message, available_categories)
        if len(filtered) == 1:
            cats = filtered
            needs_clarification = False
        elif len(filtered) < len(available_categories):
            candidate_categories = filtered
            ctype = "category_ambiguous"
            question = f"Hai detto «{message}»: intendi una di queste categorie?"
        else:
            # No category keyword match
            if matched_suppliers:
                # Brand is enough to proceed for planning
                needs_clarification = False
            else:
                ctype = "no_category_planning" if intent == "planning" else None
                question = (
                    "Puoi specificare su quali prodotti vuoi fare la pianificazione?"
                    if intent == "planning"
                    else "Puoi specificare su quali prodotti e quale periodo ti interessa?"
                )
    else:
        if matched_suppliers:
            needs_clarification = False
        else:
            ctype = "no_category_planning" if intent == "planning" else None
            question = (
                "Puoi specificare su quali prodotti vuoi fare la pianificazione?"
                if intent == "planning"
                else "Puoi specificare su quali prodotti e quale periodo ti interessa?"
            )

    return {
        "intent": intent,
        "product_filter": {
            "categories": cats,
            "supplier_names": matched_suppliers,
            "price_min": None,
            "price_max": None,
        },
        "groupby": groupby,
        "years": None,
        "external_factors": "",
        "recommendation_filter": recommendation_filter,
        "needs_clarification": needs_clarification,
        "clarification_question": question,
        "clarification_type": ctype,
        "proposed_filter": None,
        "candidate_categories": candidate_categories,
    }
