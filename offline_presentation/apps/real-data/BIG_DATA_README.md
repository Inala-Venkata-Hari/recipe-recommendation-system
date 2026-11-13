# Big Supermarket Dataset Experiment (isolated branch)

**Branch:** `small-test-big-data` (copied from `small-test`). Neither `small-test` nor `main` has been changed.

## Public data sources reviewed

1. **BigBasket Products Dataset** — third-party public snapshot describing ~27,555 Indian supermarket product listings. Columns include product name, category, subcategory, brand, sale price, MRP, type and rating. Reference: https://github.com/veer-bajpai/BigBasket-Exploratory-Data-Analysis--EDA-
2. **Alternative BigBasket CSV repository** — https://github.com/arnavification/bigbasket_sql, which documents `data/bigbasket.csv` and a smaller sample dataset.
3. **Instacart Market Basket Analysis** — actual anonymized grocery orders, useful for a separate co-purchase model, but it is not Indian BigBasket inventory or price data: https://zenodo.org/records/2654444

The BigBasket datasets are shared by third parties. Their observation dates, completeness, permission to redistribute, and license must be checked before redistribution or live commercial use. No claim of BigBasket endorsement or official API access is made.

## Import & explore

Obtain a copy of the public BigBasket CSV from the source publisher, then in this branch run:

```bash
git switch small-test-big-data
pip install -r requirements.txt
python import_bigbasket.py --input ~/Downloads/bigbasket.csv
streamlit run big_data_dashboard.py
```

For CSVs hosted at a direct downloadable URL, you can instead supply `--url https://...csv` when your computer has network access.

The importer accepts either of the documented BigBasket column variants (such as `product`/`product_name`, `brand`/`brand_name`). It removes blank or nonpositive sale prices, removes identical product/brand/price/type records, normalizes names, tags likely grocery rows and extracts explicit *single-pack* gram/kilogram weights. It computes `listed_price_per_100g` only when the pack size can be unambiguously read. Price is in INR in the BigBasket source. No taxes, discount rules or current price are inferred.

Outputs are isolated under `data/bigbasket_import/`:

- `product_catalog.csv` — normalized actual third-party catalog listings, with provenance.
- `import_summary.json` — counts, source and time of import.

**The source CSV is not bundled in the repo** because no reuse/redistribution license was confirmed. On 2026-11-08, a third-party processed snapshot was downloaded locally from `https://raw.githubusercontent.com/arnavification/bigbasket_sql/main/data.csv`. It contains 26,127 source rows, not the approximately 27,555 rows advertised for the original dataset. The existing importer produced 26,117 distinct valid listings, 12,801 heuristic grocery candidates and 139 listings with explicitly parseable mass-based pack sizes. Raw data, generated outputs and the source/hash manifest remain local and are ignored by Git. This import is not yet connected to `app.py`.

## Relationship to the recipe recommender

The original `app.py` still uses its own `RECIPE_DATA_DIR` dataset. This import does **not** replace recipe ingredients with supermarket SKUs, nor does it overwrite the existing ingredient price catalog: branded packs, units, size variants and recipe ingredients require an explicit reviewed mapping before reliable per-recipe pricing.

A BigBasket product listing does not contain `stock_qty`, `required_qty`, `unit_cost`, `expiry_date`, or sales transactions. The seller markdown engine therefore cannot be validated on actual BigBasket inventory using this dataset alone. Do not fill missing retailer fields with fake values labelled real.

## DSF experiments to add once the original datasets are present

- Catalog data quality: invalid prices, missing ratings, pack parseability, category distribution.
- Product-level historical pricing analysis: discounts vs MRP, brand/category variance, price-per-100g comparability.
- Recipe-to-product matching: reviewed matches and coverage/precision metrics; ambiguous matches stay unmatched.
- Separate Instacart experiment: association rules (support, confidence, lift) with a temporal customer-level evaluation.
- Seller decision comparison: synthetic inventory urgency baseline vs heuristic changes; no real sales uplift claims without outcomes.


## Selected replacement recipe dataset

The main app now prefers the locally imported DataHive real recipe profile (39,447 records) over synthetic_demo. See [RECIPE_DATA_COMPARISON.md](RECIPE_DATA_COMPARISON.md) for the measured comparison, licensing, missing metadata and reproduction command. Run `python import_real_recipes.py --download` to recreate the profile on another machine. Recipe-to-BigBasket mapping is still pending; real recipe prices and seller batches are not invented.


## Active quantity-aware price source and recipe filter

The app now uses [BigBasket Products by Chinmay Shanbhag](https://www.kaggle.com/datasets/chinmayshanbhag/big-basket-products), version 1, a historical listing snapshot last updated by its publisher on 2022-08-21. The actual file has 8,208 products and a separate Quantity column; 1,761 food listings have positive prices and exact gram/kg pack quantities.

Reproduce the current local profile:

```bash
python import_real_recipes.py --download
python import_bigbasket_quantity.py --download
python build_price_compatible_recipes.py
streamlit run app.py
```

The price downloader verifies the source CSV checksum. Volume/piece/multipack listings, non-food categories and invalid prices are excluded. Product URLs, original quantities, source prices and explicit ingredient mapping methods are retained. `product_ingredient_aliases.json` contains exact named-product aliases; no fuzzy name matching is used. Unlisted exact ingredient/product names may match literally, subject to `product_mapping_exclusions.json` for contextually incorrect products.

The imported catalog currently prices **75 recipe ingredient names**. The strict full-quantity/full-price rule initially retained 14 recipes, but further checks excluded incomplete recipe records, product-state mismatches and misleading literal matches (including dried pineapple and cream-filled wafers). The active profile now retains **6 recipes**, all with calculable ingredient costs, out of 39,447 source records. The excluded-recipe and missing-price reports remain local. `recipe_quality_exclusions.json` documents reviewed source issues. These checks do not establish the accuracy of every upstream recipe or measured food yield.

`BigBasket-priced recipes only` is the default profile and its sourced price catalog is read-only. Manual/synthetic prices cannot enter it through the editor. Source archives and the separate synthetic demo are preserved. Catalog rates are prorated historical INR/100g estimates; costs do not include pack-size purchase minimums, preparation yield, taxes or delivery. Cooking time and verified per-serving calorie basis remain unknown and are not fabricated.

Raw and generated third-party data remain ignored by Git, including `data/bigbasket_quantity/` and `data/price_compatible_recipes/`. No reuse license was confirmed for the inspected grocery data; source files are not redistributed by this change. Seller acquisition costs, stock and expiry must still be supplied separately.
