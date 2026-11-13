"""Standalone terminal application for creating custom recipes."""
import argparse
import csv
import json
from pathlib import Path

DEFAULT_OUTPUT = Path(__file__).parent / "data" / "custom_recipes.csv"


def main():
    parser = argparse.ArgumentParser(description="Create a recipe independently of the Streamlit app.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    name = input("Recipe name: ").strip()
    if not name:
        raise SystemExit("Recipe name is required.")
    servings = input("Servings [2]: ").strip() or "2"
    minutes = input("Cooking time in minutes [30]: ").strip() or "30"
    ingredients = []
    print("Enter ingredients. Leave ingredient name blank when finished.")
    while True:
        ingredient = input("Ingredient: ").strip()
        if not ingredient:
            break
        try:
            quantity = float(input("Quantity in grams: ").strip())
            if quantity <= 0:
                raise ValueError
        except ValueError:
            print("Enter a positive numeric quantity.")
            continue
        ingredients.append({"name": ingredient, "quantity_g": quantity})
    if not ingredients:
        raise SystemExit("At least one ingredient is required.")
    steps = []
    print("Enter instructions, one step at a time. Blank line ends input.")
    while True:
        step = input(f"Step {len(steps)+1}: ").strip()
        if not step:
            break
        steps.append(step)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    exists = args.output.exists()
    with args.output.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["name", "servings", "minutes", "ingredients", "steps"])
        if not exists:
            writer.writeheader()
        writer.writerow({"name": name, "servings": servings, "minutes": minutes,
                         "ingredients": json.dumps(ingredients), "steps": json.dumps(steps)})
    print(f"Recipe saved to {args.output}")


if __name__ == "__main__":
    main()
