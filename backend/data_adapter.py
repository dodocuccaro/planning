from abc import ABC, abstractmethod
from collections import defaultdict


class DataAdapter(ABC):
    @abstractmethod
    def get_categories(self) -> list:
        """Return all unique category values."""

    @abstractmethod
    def get_attributes(self) -> list:
        """Return groupable attribute names that have data."""

    @abstractmethod
    def get_years(self) -> list:
        """Return all years in the data."""

    @abstractmethod
    def get_suppliers(self) -> list:
        """Return all unique supplier_name values."""

    @abstractmethod
    def query(self, categories=None, price_min=None, price_max=None,
              years=None, groupby=None, supplier_names=None) -> list:
        """
        Returns rows: [{"label": str, "year": int, "sales": float}]
        label = groupby value if groupby set, else product_name.
        """

    @abstractmethod
    def get_planning_units(self, categories=None, price_min=None,
                           price_max=None, years=None, groupby=None,
                           supplier_names=None) -> list:
        """Returns list of product dicts in planner.analyze() format."""


class InMemoryAdapter(DataAdapter):
    def __init__(self, products: list):
        self._products = products

    def get_categories(self) -> list:
        return sorted({str(p.get("category") or "") for p in self._products if p.get("category")})

    def get_attributes(self) -> list:
        candidates = ["color", "size", "sales_channel", "supplier_name", "category"]
        return [a for a in candidates if any(p.get(a) for p in self._products)]

    def get_years(self) -> list:
        years = set()
        for p in self._products:
            for h in p.get("history", []):
                years.add(h["year"])
        return sorted(years)

    def get_suppliers(self) -> list:
        return sorted({str(p.get("supplier_name") or "") for p in self._products if p.get("supplier_name")})

    def _filter(self, categories, price_min, price_max, supplier_names=None):
        result = self._products
        if categories:
            result = [p for p in result if (p.get("category") or "") in categories]
        if price_min is not None:
            result = [p for p in result if float(p.get("unit_cost") or 0) >= price_min]
        if price_max is not None:
            result = [p for p in result if float(p.get("unit_cost") or 0) <= price_max]
        if supplier_names:
            result = [p for p in result if (p.get("supplier_name") or "") in supplier_names]
        return result

    def _get_label(self, p, groupby):
        if groupby and p.get(groupby):
            return str(p[groupby])
        return p["product_name"]

    def query(self, categories=None, price_min=None, price_max=None,
              years=None, groupby=None, supplier_names=None) -> list:
        filtered = self._filter(categories, price_min, price_max, supplier_names)
        target_years = set(years) if years else None

        agg = defaultdict(lambda: defaultdict(float))
        for p in filtered:
            label = self._get_label(p, groupby)
            for h in p.get("history", []):
                yr = h["year"]
                if target_years and yr not in target_years:
                    continue
                sales = max(0.0,
                    float(h.get("opening_stock", 0) or 0)
                    + float(h.get("qty_purchased", 0) or 0)
                    - float(h.get("closing_stock", 0) or 0)
                )
                agg[label][yr] += sales

        rows = []
        for label, year_data in agg.items():
            for yr, sales in sorted(year_data.items()):
                rows.append({"label": label, "year": yr, "sales": round(sales, 1)})
        return rows

    def get_planning_units(self, categories=None, price_min=None,
                           price_max=None, years=None, groupby=None,
                           supplier_names=None) -> list:
        filtered = self._filter(categories, price_min, price_max, supplier_names)
        target_years = set(years) if years else None

        units = defaultdict(lambda: {
            "sales_by_year":    defaultdict(float),
            "ordered_by_year":  defaultdict(float),
            "cost_total":       0.0,
            "cost_qty":         0.0,
            "price_total":      0.0,
            "price_qty":        0.0,
            "current_stock":    0.0,
        })

        for p in filtered:
            label = self._get_label(p, groupby)
            u = units[label]
            u["current_stock"] = max(u["current_stock"], float(p.get("current_stock", 0) or 0))

            # Accumulate price/cost totals for weighted-average unit economics
            uc = p.get("unit_cost")
            up = p.get("unit_price")
            for h in p.get("history", []):
                yr = h["year"]
                if target_years and yr not in target_years:
                    continue
                sold    = max(0.0, float(h.get("qty_purchased", 0) or 0))
                ordered = float(h.get("qty_ordered", 0) or 0)
                u["sales_by_year"][yr]   += sold
                u["ordered_by_year"][yr] += ordered
                if uc:
                    u["cost_total"] += uc * (ordered or sold)
                    u["cost_qty"]   += (ordered or sold)
                if up:
                    u["price_total"] += up * sold
                    u["price_qty"]   += sold

        result = []
        for label, data in units.items():
            years_sorted = sorted(data["sales_by_year"].keys())
            history = [
                {
                    "year":          yr,
                    "opening_stock": 0,
                    "qty_purchased": data["sales_by_year"][yr],
                    "closing_stock": 0,
                    "qty_ordered":   data["ordered_by_year"].get(yr, 0.0),
                }
                for yr in years_sorted
            ]
            unit_cost  = round(data["cost_total"]  / data["cost_qty"],  2) if data["cost_qty"]  > 0 else None
            unit_price = round(data["price_total"] / data["price_qty"], 2) if data["price_qty"] > 0 else None
            gross_margin = round((unit_price - unit_cost) / unit_price * 100, 1) if (unit_cost and unit_price and unit_price > 0) else None

            result.append({
                "product_code":     label,
                "product_name":     label,
                "current_stock":    data["current_stock"],
                "unit_cost":        unit_cost,
                "unit_price":       unit_price,
                "gross_margin_pct": gross_margin,
                "history":          history,
            })
        return result
