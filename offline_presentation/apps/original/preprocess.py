"""Create reduced recipe and ingredient-frequency classification datasets."""
import ast
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
            "ingredient_frequency_category": category,
        })
    pd.DataFrame(rows).sort_values("recipe_frequency", ascending=False).to_csv(
        DATA_DIR / "ingredients_classified.csv", index=False
    )
    print("Created " + str(len(df)) + " recipes and " + str(len(rows)) + " unique ingredients.")


if __name__ == "__main__":
    main()
