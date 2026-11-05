"""Generate a small, deterministic dataset for isolated app experiments.

All records are synthetic examples, not real market prices or nutritional facts.
Run: python generate_synthetic_data.py
"""
from pathlib import Path
import ast
from datetime import date, timedelta
import pandas as pd

ROOT = Path(__file__).parent
OUTPUT = ROOT / "data" / "synthetic_demo"

RECIPES = [
    ("S001", "Tomato Rice", ["rice", "tomato", "onion", "garlic", "cumin"], 25, 360),
    ("S002", "Vegetable Pulao", ["rice", "carrot", "peas", "onion", "ginger", "cumin"], 35, 410),
    ("S003", "Chickpea Curry", ["chickpeas", "tomato", "onion", "garlic", "ginger", "turmeric"], 40, 390),
    ("S004", "Paneer Masala", ["paneer", "tomato", "onion", "garlic", "cream", "chilli powder"], 30, 450),
    ("S005", "Egg Fried Rice", ["rice", "egg", "carrot", "peas", "soy sauce", "spring onion"], 20, 430),
    ("S006", "Lemon Rice", ["rice", "lemon", "peanuts", "curry leaves", "mustard seeds"], 20, 340),
    ("S007", "Potato Pea Masala", ["potato", "peas", "tomato", "onion", "turmeric", "cumin"], 30, 320),
    ("S008", "Chicken Tomato Curry", ["chicken", "tomato", "onion", "garlic", "ginger", "chilli powder"], 45, 520),
    ("S009", "Mixed Vegetable Noodles", ["noodles", "carrot", "cabbage", "capsicum", "soy sauce", "garlic"], 25, 380),
    ("S010", "Dal Tadka", ["lentils", "tomato", "onion", "garlic", "cumin", "turmeric"], 35, 300),
    ("S011", "Paneer Pulao", ["rice", "paneer", "peas", "onion", "ginger", "cumin"], 35, 470),
    ("S012", "Chickpea Salad", ["chickpeas", "tomato", "cucumber", "onion", "lemon", "coriander"], 15, 280),
    ("S013", "Garlic Noodles", ["noodles", "garlic", "cabbage", "capsicum", "soy sauce"], 18, 350),
    ("S014", "Chicken Fried Rice", ["rice", "chicken", "egg", "carrot", "spring onion", "soy sauce"], 30, 490),
    ("S015", "Potato Lemon Chaat", ["potato", "lemon", "peanuts", "coriander", "chilli powder"], 15, 260),
]

QUANTITY_G = {
    "rice": 150,
    "tomato": 100,
    "onion": 60,
    "garlic": 10,
    "cumin": 3,
    "carrot": 60,
    "peas": 50,
    "ginger": 10,
    "chickpeas": 140,
    "turmeric": 3,
    "paneer": 150,
    "cream": 40,
    "chilli powder": 4,
    "egg": 100,
    "soy sauce": 15,
    "spring onion": 20,
    "lemon": 30,
    "peanuts": 25,
    "curry leaves": 3,
    "mustard seeds": 3,
    "potato": 180,
    "chicken": 180,
    "noodles": 150,
    "cabbage": 70,
    "capsicum": 60,
    "lentils": 140,
    "cucumber": 70,
    "coriander": 10
}


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    recipe_rows = []
    counts = {}
    for recipe_id, name, ingredients, minutes, calories in RECIPES:
        recipe_rows.append({
            "id": recipe_id,
            "name": name,
            "ingredients": repr(ingredients),
            "ingredient_quantities": repr([
                {"name": ingredient, "quantity_g": QUANTITY_G[ingredient]}
                for ingredient in ingredients
            ]),
            "servings": 2,
            "n_ingredients": len(ingredients),
            "minutes": minutes,
            "nutrition": repr([calories, 0, 0, 0, 0, 0, 0]),
            "tags": repr(["synthetic", "demo"]),
            "steps": repr([f"Prepare {name.lower()} ingredients.", "Cook until ready and serve."]),
            "calories_per_serving": calories,
        })
        for ingredient in set(ingredients):
            counts[ingredient] = counts.get(ingredient, 0) + 1

    pd.DataFrame(recipe_rows).to_csv(OUTPUT / "recipes_cleaned.csv", index=False)
    total = len(recipe_rows)
    classified = pd.DataFrame([
        {
            "ingredient_name": name,
            "recipe_frequency": count,
            "frequency_ratio": round(count / total, 4),
            "ingredient_frequency_category": ("Common" if count / total >= .25 else "Moderately common" if count / total >= .10 else "Specialized" if count / total >= .03 else "Rare / recipe-specific"),
        }
        for name, count in counts.items()
    ]).sort_values(["recipe_frequency", "ingredient_name"], ascending=[True, True])
    classified.to_csv(OUTPUT / "ingredients_classified.csv", index=False)

    # Prices and nutrition below are deliberately fictional test values.
    catalog = pd.DataFrame([
        {"ingredient_name": name, "price_per_100g": round(4 + (i * 1.7), 2), "kcal_per_100g": 40 + i * 13}
        for i, name in enumerate(sorted(counts))
    ])
    catalog.to_csv(OUTPUT / "ingredient_catalog.csv", index=False)

    # Fixed snapshot makes presentation results reproducible. Units are 100 g packs.
    today = date(2026, 11, 5)
    rates = dict(zip(catalog.ingredient_name, catalog.price_per_100g))
    scenarios = [
        # ingredient, stock, reserve, age, days left, daily sales, holding target, window, cost fraction, label
        ("rice", 180, 40, 2, 180, 8, 120, 30, .65, "Fresh staple"),
        ("tomato", 150, 35, 8, 2, 12, 7, 7, .60, "Near expiry / excess stock"),
        ("onion", 200, 50, 18, 8, 8, 14, 14, .65, "Aging slow mover"),
        ("paneer", 65, 25, 5, 1, 5, 5, 5, .75, "Urgent perishable"),
        ("noodles", 90, 20, 12, 90, 2, 90, 21, .65, "Shelf-stable surplus"),
        ("chickpeas", 110, 30, 15, 120, 2, 90, 30, .70, "Shelf-stable surplus"),
        ("chicken", 45, 40, 3, 2, 8, 4, 4, .97, "Very narrow margin"),
        ("cream", 25, 5, 8, -1, 2, 5, 5, .65, "Expired: must exclude"),
        ("cucumber", 0, 0, 2, 5, 3, 7, 4, .65, "Zero stock: must exclude"),
        ("lentils", 30, 30, 0, 120, 2, 90, 30, .65, "Fresh, no excess: no urgency"),
        ("capsicum", 60, 10, 9, 3, 4, 7, 7, .65, "Specialized ingredient / aging"),
        ("peas", 80, 20, 10, 5, 5, 10, 7, .65, "Moderately common / surplus"),
    ]
    records = []
    for i, (name, stock, reserve, age, left, sales, target, window, fraction, label) in enumerate(scenarios):
        records.append(dict(ingredient_name=name, batch_id=f"DEMO-{i+1:02}",
            stock_qty=stock, required_qty=reserve, unit_cost=round(rates[name]*fraction, 2),
            unit_price=rates[name], stock_unit="100 g pack", received_date=(today-timedelta(days=age)).isoformat(),
            expiry_date=(today+timedelta(days=left)).isoformat(), avg_daily_sales=sales,
            target_holding_days=target, markdown_window_days=window, scenario=label))
    pd.DataFrame(records).to_csv(OUTPUT / "seller_inventory.csv", index=False)
    pd.DataFrame(columns=["ingredient_name", "enabled", "notes"]).to_csv(OUTPUT / "pantry_ingredients.csv", index=False)
    pd.DataFrame(columns=["ingredient_name", "recipe_frequency", "frequency_ratio"]).to_csv(OUTPUT / "pantry_candidates.csv", index=False)
    print(f"Generated {len(recipe_rows)} synthetic recipes and {len(counts)} ingredients in {OUTPUT}")
    print("All prices and nutrition values are fictional test values.")

if __name__ == "__main__":
    main()
