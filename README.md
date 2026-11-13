# Ready-to-run transfer

Moving laptops? Follow [NEW_LAPTOP.md](NEW_LAPTOP.md). The `offline_presentation/` folder includes all three demos, data, the trained experimental ML model, slides and a setup script.

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

The discount engine uses age-aware dynamic markdowns. Each batch receives an urgency score: 35% stock age / target holding days, 40% expiry risk (1 minus days remaining / markdown window), and 25% expected unsold stock / current stock. Scores are bounded to 0–1. Expected unsold stock is max(0, stock minus average daily sales times days remaining). Without demand or expiry data, the excess signal uses the surplus ratio. Missing age/expiry signals are omitted and remaining weights renormalized. These weights are configurable implementation assumptions, not fitted demand estimates.

Optional inventory columns: `batch_id`, `received_date`, `expiry_date` (ISO dates), `avg_daily_sales`, `target_holding_days`, `markdown_window_days`. Sales and stock must use the same unit; cost and price are per stock unit. Set holding targets and markdown windows per ingredient. Assessment date is selectable in the seller tab. Invalid dates, future receipts, negative/nonfinite required numeric values, and batches expiring on or before assessment date are excluded. Missing optional values fall back rather than being inferred.

Offers combine 2–4 distinct ingredients, one stock unit each, using the earliest-expiring eligible batch per ingredient (oldest receipt breaks ties). Proposed discount equals maximum discount times average urgency. The existing gross-margin floor caps the offer; discounts round down to 0.1% to preserve that floor. Offers display urgency and recipes using all offered ingredients. Scores are a prioritization heuristic, not a guarantee of increased sales. Evaluate units sold, waste and gross profit against the surplus-only baseline before tuning weights.

Synthetic demo inventory is a reproducible snapshot dated 2026-11-05. The seller tab defaults to that assessment date for this dataset. `python generate_synthetic_data.py` recreates the same snapshot and rewrites all synthetic files, including pantry files.

## Customer recommendations

- Ingredients are selected individually; the previous bulk/multiple-add control has been removed.
- At least three cart ingredients are required to show recommendations.
- Customers can sort recommendations using exactly three categories: **Calories**, **Time Taken**, and **Budget Friendly**.
- Calories: lowest calories per serving first; ties use fewer additional ingredients, then shorter cooking time.
- Time Taken: shortest cooking time first; ties use fewer additional ingredients, then lower estimated recipe cost when available, then lower calories.
- Budget Friendly: lowest reliable recipe-level cost first; ties use fewer additional ingredients, then shorter cooking time.
- Missing primary values are placed last. Sorting is stable when all available criteria tie.
- Budget Friendly sorting requires reliable recipe-level costs. The Food.com source recipes do not include dependable ingredient quantities, so the app clearly reports when cost sorting is unavailable rather than inventing estimates.
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

Run `python preprocess.py` to create or update `data/ingredient_catalog.csv`. It automatically adds one row for every ingredient found in the recipe dataset, with columns `ingredient_name,price_per_100g,kcal_per_100g`. Existing prices and nutrition values are preserved when preprocessing is run again.

Open the **Ingredient price catalog** tab in the app and enter each ingredient's market price per 100 g (and calories per 100 g when available). For example, if rice costs ₹60 per kg, enter ₹6 per 100 g. The customer cart then accepts a quantity in grams and calculates each ingredient's estimated cost as:

`item cost = (quantity in grams / 100) × price per 100 g`

The catalog is ingredient-level data, not recipe-level data. A numeric recipe estimate still requires the quantity of every ingredient. The Food.com source dataset generally provides ingredient names without dependable quantities, so existing source recipes cannot yet receive exact ingredient-derived costs. Missing data is reported rather than fabricated.

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


## Isolated synthetic test environment

The `small-test` branch includes a small, reproducible dataset so features can be tested without the full Food.com source file or any real retailer data.

Generate it:

```bash
python generate_synthetic_data.py
```

Run the app against the synthetic data (the original `data/` directory is not changed):

**Linux / macOS**
```bash
RECIPE_DATA_DIR=data/synthetic_demo streamlit run app.py
```

**Windows PowerShell**
```powershell
$env:RECIPE_DATA_DIR = "data/synthetic_demo"
streamlit run app.py
```

The generated dataset contains 15 sample recipes, ingredient-frequency records, an ingredient catalog, and seller inventory rows. Prices and nutrition values are intentionally fictional and must never be treated as market or dietary facts. To return to the normal dataset, unset `RECIPE_DATA_DIR` and run the app normally.


### Classification-based discount parameters

The seller tab joins inventory to the active `ingredients_classified.csv` using normalized ingredient names. Numeric `frequency_ratio` determines category: >=0.25 Common (multiplier 1.0), >=0.10 Moderately common (1.1), >=0.03 Specialized (1.2), otherwise Rare / recipe-specific (1.3). Input category labels are recomputed to avoid inconsistent labels. Missing/invalid ratios and conflicting duplicate classifications use the neutral unclassified multiplier 1.0.

Per-item discount priority = min(1, inventory urgency × category multiplier). Combo discount = maximum discount × mean item priority, further capped by the existing margin floor and rounded down. Offers sort by this adjusted priority. Classification alone cannot make zero-urgency or expired inventory eligible. This policy assumes less recipe versatility warrants a modest markdown boost; multipliers are heuristic policy constants, not learned demand elasticities. Classification does not determine shelf life, costs, or sales velocity. Without classification input the Python API preserves previous behavior. The app displays the derived parameter table and per-batch scores.


### Seller decision dashboard and presentation data

Offers display original/offer price, acquisition cost, profit, savings, gross margin, margin-cap status, quantities, batch IDs and age/expiry/excess/classification breakdowns. Download all proposed offers as CSV. Each row is an alternative offer, not a stock allocation; shared inventory means totals must not be added. Selling prices round upward to cents after percentage rounding to preserve the margin floor.

The improved demo includes 12 inventory scenarios in 100 g packs, with unit prices matching the 28-entry ingredient catalog. Cases include fresh, aging, urgent expiry, low margin, expired, zero-stock and no-urgency items. Classification labels now correctly follow all frequency thresholds. Recipe cost estimation is shared between app and tests. See [PRESENTATION_GUIDE.md](PRESENTATION_GUIDE.md) for the walkthrough, provenance and limitations.


### Simulated checkout

Customer recipe cards can add discounted combos to the cart. Supported combos specify 100 g packs and unique inventory batches. Selected combos are revalidated against regenerated offers, batch stock, current prices/settings and cart quantities at checkout. Overlapping ingredients cannot receive multiple combo discounts. Extra grams and regular items use catalog estimates. The checkout shows regular total, savings and final total, and produces a downloadable simulated receipt. No payment or persistent stock deduction occurs. Reset demo clears this session's cart, combos, uploads, receipt and controls without modifying saved CSVs.


### Publish promotions before the customer demonstration

In the seller tab, select draft offers, choose an exclusive promotion end date and click Publish selected offers. Customers and checkout use only active published offers. End dates are capped at batch expiry. Pause selected offers withdraws them immediately on the next rerun; selected carts must remove invalid combos before checking out. Changed draft prices, costs, quantities or eligibility require republishing. Published snapshots are saved in the active data directory as published_offers.json and survive app restarts and session reset. Reset demo does not erase publications. This is a local demonstration with shared files, not an authenticated multi-user seller service.


### Promotion discovery and activity history

Sellers can select all draft offers for bulk publishing, or pick individual offers. Publication activity history records changed publish/pause events with India-time timestamps, assessment date, combo price, discount and end date; it can be exported as CSV. This local demo history is not an authenticated audit trail. History and publications persist across session resets and app restarts.

Customers can browse active published offers before choosing recipes. Search by ingredient, sort by highest rupee savings, lowest bundle price or ending soon, and navigate eight offers per page. Add this published combo updates the cart and effective price; overlapping selections are disabled. A paused or invalid offer is excluded from the browser and blocks a previously selected discounted checkout until removed.


### Schedule-aware combo discovery

Published offers can be prioritized by recipes that fit the selected schedule: busy/short break <=30 minutes, late study/work <=20 minutes, family >=2 recorded servings, after workout contains lentils/chickpeas/paneer/egg/chicken (an ingredient heuristic, not a calculated protein claim). A matching recipe must use every ingredient in the bundle. The customer sees supporting recipe names and can turn prioritization off. Unmatched offers remain available. Recipe order still uses ascending additional-item count, and automatic combo selection still maximizes savings. Schedule context changes neither pricing nor publication/checkout eligibility.


## Full USDA USD workflow

Run `python build_usda_trial.py --download` and `streamlit run usda_trial.py --server.port 8503` for the code-linked USDA customer/seller experiment. It includes seller batches/uploads/edits, age/frequency discounts, publication/pause/history, price overrides, customer automatic best-savings combos, simulated checkout and printable USD invoices. USDA reference facts remain separate from user-entered or explicitly simulated inventory. See [USDA_TRIAL.md](USDA_TRIAL.md) for a reproducible demonstration, schedule rules and data limits. The original INR app remains available separately.
