"""Create reduced recipe and ingredient-frequency classification datasets."""
import ast
import math
from pathlib import Path

import pandas as pd

from ingredient_normalization import normalize_ingredient, normalize_ingredient_list

ROOT = Path(__file__).parent
SOURCE = ROOT / "RAW_recipes.csv"
DATA_DIR = ROOT / "data"
MAX_RECIPES = 5000
COLUMNS = ["id", "name", "ingredients", "n_ingredients", "minutes", "nutrition", "tags", "steps"]


def parse_list(value):
    if isinstance(value, list):
        return value
    if pd.isna(value):
        return []
    try:
        result = ast.literal_eval(value)
        return result if isinstance(result, list) else []
    except (ValueError, SyntaxError, TypeError):
        return []


def calories_from_nutrition(values):
    if not values:
        return None
    try:
        result = float(values[0])
        return result if result >= 0 else None
    except (ValueError, TypeError):
        return None



def update_ingredient_catalog(ingredient_names):
    """Create catalog rows for all known ingredients while preserving entered values."""
    catalog_path = DATA_DIR / "ingredient_catalog.csv"
    columns = ["ingredient_name", "price_per_100g", "kcal_per_100g"]
    if catalog_path.exists():
        existing = pd.read_csv(catalog_path)
        for column in columns:
            if column not in existing.columns:
                existing[column] = pd.NA
        existing = existing[columns]
    else:
        existing = pd.DataFrame(columns=columns)

    existing["_key"] = existing["ingredient_name"].map(normalize_ingredient)
    known = set(existing["_key"].dropna())
    additions = [
        {"ingredient_name": name, "price_per_100g": pd.NA, "kcal_per_100g": pd.NA}
        for name in sorted(set(ingredient_names) - known)
    ]
    existing = pd.concat([existing[columns], pd.DataFrame(additions)], ignore_index=True)
    existing = existing.drop_duplicates(subset=["ingredient_name"], keep="first")
    existing = existing.sort_values("ingredient_name", key=lambda col: col.str.casefold(), kind="stable")
    existing.to_csv(catalog_path, index=False)
    return len(additions)


def main():
    if not SOURCE.exists():
        raise FileNotFoundError("Put RAW_recipes.csv in the project root beside preprocess.py.")
    DATA_DIR.mkdir(exist_ok=True)
    df = pd.read_csv(SOURCE)
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError("Source CSV is missing columns: " + str(sorted(missing)))
    df = df[COLUMNS].dropna(subset=["id", "name", "ingredients"]).copy()
    df = df.drop_duplicates(subset=["id"])
    for column in ("ingredients", "nutrition", "tags", "steps"):
        df[column] = df[column].apply(parse_list)
    df["ingredients"] = df["ingredients"].apply(normalize_ingredient_list)
    df["n_ingredients"] = df["ingredients"].apply(len)
    df["minutes"] = pd.to_numeric(df["minutes"], errors="coerce")
    df = df[(df["n_ingredients"] >= 5) & df["minutes"].notna() & (df["minutes"] > 0)]
    df = df.sample(n=min(MAX_RECIPES, len(df)), random_state=42).reset_index(drop=True)
    df["calories_per_serving"] = df["nutrition"].apply(calories_from_nutrition)
    df.to_csv(DATA_DIR / "recipes_cleaned.csv", index=False)

    frequencies = {}
    for items in df["ingredients"]:
        for item in set(items):
            frequencies[item] = frequencies.get(item, 0) + 1
    total = len(df)
    rows = []
    for item, count in frequencies.items():
        ratio = count / total if total else 0
        if ratio >= 0.25:
            category = "Common"
        elif ratio >= 0.10:
            category = "Moderately common"
        elif ratio >= 0.03:
            category = "Specialized"
        else:
            category = "Rare / recipe-specific"
        rows.append({
            "ingredient_name": item,
            "recipe_frequency": count,
            "frequency_ratio": round(ratio, 4),
            "distinctiveness_score": round(math.log((total + 1) / (count + 1)), 4),
            "ingredient_frequency_category": category,
        })
    classified = pd.DataFrame(rows)
    classified = classified.sort_values(
        ["recipe_frequency", "distinctiveness_score", "ingredient_name"],
        ascending=[False, False, True],
        kind="stable",
    )
    classified.to_csv(DATA_DIR / "ingredients_classified.csv", index=False)

    # High-frequency ingredients become review candidates, never automatic pantry staples.
    candidates = classified[classified["frequency_ratio"] >= 0.25][["ingredient_name", "recipe_frequency", "frequency_ratio"]].copy()
    candidates = candidates.sort_values(["frequency_ratio", "ingredient_name"], ascending=[False, True], kind="stable")
    candidates.to_csv(DATA_DIR / "pantry_candidates.csv", index=False)

    added = update_ingredient_catalog(frequencies.keys())
    print("Created " + str(len(df)) + " recipes and " + str(len(rows)) + " unique ingredients.")
    print("Ingredient catalog: " + str(DATA_DIR / "ingredient_catalog.csv"))
    print("Added " + str(added) + " new ingredients; enter each price per 100 g.")


if __name__ == "__main__":
    main()
