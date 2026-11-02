"""Generate a small, deterministic dataset for isolated app experiments.

All records are synthetic examples, not real market prices or nutritional facts.
Run: python generate_synthetic_data.py
"""
from pathlib import Path
import ast
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
            "ingredient_frequency_category": "Common" if count / total >= .25 else "Specialized",
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

    inventory = pd.DataFrame([
        {"ingredient_name": "rice", "stock_qty": 180, "required_qty": 40, "unit_cost": 42, "unit_price": 60},
        {"ingredient_name": "tomato", "stock_qty": 150, "required_qty": 35, "unit_cost": 18, "unit_price": 30},
        {"ingredient_name": "onion", "stock_qty": 200, "required_qty": 50, "unit_cost": 20, "unit_price": 34},
        {"ingredient_name": "paneer", "stock_qty": 65, "required_qty": 25, "unit_cost": 210, "unit_price": 280},
        {"ingredient_name": "noodles", "stock_qty": 90, "required_qty": 20, "unit_cost": 28, "unit_price": 45},
        {"ingredient_name": "chickpeas", "stock_qty": 110, "required_qty": 30, "unit_cost": 55, "unit_price": 78},
        {"ingredient_name": "chicken", "stock_qty": 45, "required_qty": 40, "unit_cost": 170, "unit_price": 210},
    ])
    inventory.to_csv(OUTPUT / "seller_inventory.csv", index=False)
    pd.DataFrame(columns=["ingredient_name", "enabled", "notes"]).to_csv(OUTPUT / "pantry_ingredients.csv", index=False)
    pd.DataFrame(columns=["ingredient_name", "recipe_frequency", "frequency_ratio"]).to_csv(OUTPUT / "pantry_candidates.csv", index=False)
    print(f"Generated {len(recipe_rows)} synthetic recipes and {len(counts)} ingredients in {OUTPUT}")
    print("All prices and nutrition values are fictional test values.")

if __name__ == "__main__":
    main()
