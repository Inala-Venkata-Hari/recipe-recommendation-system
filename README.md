# Smart Cart Recipe Recommendation & Seller Inventory System

A seller-oriented smart-cart platform. Its primary purpose is to create inventory-aware combo discounts from current stock and supply requirements; recipe recommendations help customers understand and use those combinations.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python preprocess.py
streamlit run app.py
```

Windows PowerShell: activate with `.venv\\Scripts\\Activate.ps1`.

## Seller inventory and combo discounts

Upload an inventory CSV or create `data/seller_inventory.csv` using `data/seller_inventory_template.csv`. Required columns:

- `ingredient_name`
- `stock_qty`: current stock
- `required_qty`: reserved / expected supply requirement that must be protected
- `unit_cost`: seller's cost per item/unit
- `unit_price`: normal selling price per item/unit

The discount engine considers combinations of 2–4 eligible items. An item is eligible only when stock exceeds required supply and unit price exceeds unit cost. Discount scales with the average surplus-stock ratio, is capped by the seller-configured maximum, and is further capped to preserve the configured minimum margin. These are initial configurable rules; production use should incorporate demand forecasts, expiry dates, replenishment lead time, and transaction data.

## Customer recommendations

- Ingredients are selected individually; the previous bulk/multiple-add control has been removed.
- At least three cart ingredients are required to show recommendations.
- Recipes are ranked by cart overlap, then fewer missing ingredients, then cooking time.
- Recipes requiring **zero additional ingredients** receive a prominent success highlight.
- Recipes using at least three items from a larger cart are explicitly identified.
- The ingredient selector is simplified: less-frequently used ingredients appear first, with no category-filter maze.
- Approved household pantry staples are hidden from the selector by default, but customers can opt to show and select them.
- Pantry identification is hybrid: a small manually curated core list in `app.py` defines household basics, while preprocessing generates high-frequency candidates (>=25% of recipes) for human review. Frequency alone never automatically makes an ingredient a pantry staple.
- Approved additional staples are saved in `data/pantry_ingredients.csv`; the app creates this file when the first candidates are approved. Review this file to manage household-specific assumptions.
- Run `python preprocess.py` to regenerate `data/pantry_candidates.csv` from the current recipe sample.
- Pantry ingredients remain in recipe instructions and are excluded only from the count of additional items the customer must obtain.
- Ingredient catalog prices are shown beside selected ingredients. Customers can enter a quantity in grams to see each item total and the combined selected-cart total. Recipe-level totals for existing source recipes still require recipe quantities, which the source generally does not provide, so no total is fabricated.
- Local system time selects a broad meal period. Optional schedule context refines meal suggestions; the system does not claim to detect a person's actual mood.

## Per-ingredient pricing and nutrition

Create `data/ingredient_catalog.csv` from `data/ingredient_catalog_template.csv` with columns `ingredient_name,price_per_100g,kcal_per_100g`. Prices and nutrition are stored per ingredient, not in a recipe-level lookup table.

A numeric estimate requires each recipe ingredient to have a quantity in grams. The custom recipe form and CLI collect quantities. The public Food.com source dataset generally provides ingredient names without dependable quantities, so exact ingredient-derived totals cannot be calculated for those existing recipes until quantities are supplied. Missing data is reported rather than fabricated.

## Custom recipes

- In the Streamlit app, use the **Create your recipe** tab and enter ingredient quantities in grams.
- For a separate terminal workflow, run `python create_recipe.py`. Optional: `python create_recipe.py --output path/to/recipes.csv`.
- Both workflows save recipe ingredients as structured per-ingredient records.

## Data preparation

Place Food.com `RAW_recipes.csv` beside `preprocess.py`, then run `python preprocess.py`. It creates `data/recipes_cleaned.csv`, `data/ingredients_classified.csv`, and `data/pantry_candidates.csv`. Ingredient selection is ordered by ascending recipe frequency (least frequent first); frequency categories are retained only as analysis metadata, not as customer-facing filters.

## Important limitations

- Seller inventory and ingredient prices must be supplied by the retailer; templates contain headers only.
- Discount percentages are illustrative outputs of configurable business rules, not a universal optimal pricing strategy.
- Schedule context is selected by the user; no private calendar or emotion inference is performed.
- Calories and costs are only estimated when quantity and reference data are available.
- This is a research prototype; validate pricing, stock reservations, taxes, and local food/nutrition data before commercial deployment.
