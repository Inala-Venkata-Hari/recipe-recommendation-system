"""Inventory-aware combo discount calculations for seller promotions."""
from itertools import combinations
import pandas as pd

REQUIRED = {"ingredient_name", "stock_qty", "required_qty", "unit_cost", "unit_price"}


def generate_combo_offers(inventory, max_discount=15, min_items=2, max_items=4,
                          base_discount=3, surplus_scale=12, minimum_margin_pct=5):
    """Scale discount with surplus stock, capped by configured discount and margin."""
    if inventory is None or inventory.empty or not REQUIRED.issubset(inventory.columns):
        return []
    data = inventory.copy()
    numeric = REQUIRED - {"ingredient_name"}
    for column in numeric:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=list(numeric))
    data = data[(data.stock_qty > data.required_qty) & (data.unit_price > data.unit_cost)]
    rows = data.to_dict("records")
    offers = []
    for size in range(min_items, min(max_items, len(rows)) + 1):
        for combo in combinations(rows, size):
            ratios = [(x["stock_qty"] - x["required_qty"]) / max(x["stock_qty"], 1) for x in combo]
            avg_surplus = sum(ratios) / size
            proposed = min(float(max_discount), base_discount + surplus_scale * avg_surplus)
            revenue = sum(x["unit_price"] for x in combo)
            cost = sum(x["unit_cost"] for x in combo)
            margin_cap = max(0.0, (revenue - cost - revenue * minimum_margin_pct / 100) / revenue * 100)
            discount = min(proposed, margin_cap)
            if discount <= 0:
                continue
            offers.append({"items": [str(x["ingredient_name"]) for x in combo],
                           "discount_pct": round(discount, 1), "surplus_score": avg_surplus,
                           "reason": f"Average stock surplus: {avg_surplus:.0%}; minimum margin retained."})
    return sorted(offers, key=lambda x: (-x["surplus_score"], -len(x["items"]), x["items"]))
