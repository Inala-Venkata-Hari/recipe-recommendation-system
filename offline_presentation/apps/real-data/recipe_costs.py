"""Recipe cost estimates from quantities and catalog prices."""
import pandas as pd
import math
from ingredient_normalization import normalize_ingredient


def add_recipe_cost_estimates(recipes, catalog):
    """Calculate recipe costs only when all ingredient quantities and prices exist."""
    lookup = {}
    if not catalog.empty:
        for row in catalog.itertuples():
            try:
                lookup[normalize_ingredient(row.ingredient_name)] = float(row.price_per_100g)
            except (TypeError, ValueError):
                continue

    def estimate(row):
        items = row.get("ingredient_quantities", [])
        if not isinstance(items, list) or not items:
            return None
        total = 0.0
        for item in items:
            if not isinstance(item, dict) or not item.get("name") or item.get("quantity_g") is None:
                return None
            rate = lookup.get(normalize_ingredient(item["name"]))
            if rate is None or not math.isfinite(rate) or rate < 0:
                return None
            try:
                quantity = float(item["quantity_g"])
            except (TypeError, ValueError):
                return None
            if not math.isfinite(quantity) or quantity <= 0:
                return None
            total += quantity * rate / 100
        return round(total, 2)

    results = recipes.copy()
    if results.empty:
        results["estimated_cost"] = pd.Series(dtype=float)
        results["estimated_cost_per_serving"] = pd.Series(dtype=float)
        return results
    results["estimated_cost"] = results.apply(estimate, axis=1)
    if "servings" in results.columns:
        servings = pd.to_numeric(results["servings"], errors="coerce")
    else:
        servings = pd.Series(1.0, index=results.index)
    servings = servings.where(servings > 0)
    results["estimated_cost_per_serving"] = (results["estimated_cost"] / servings).round(2)
    return results

