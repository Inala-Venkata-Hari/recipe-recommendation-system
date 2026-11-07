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

**The source CSV is not bundled in the repo** because no reuse/redistribution license was confirmed and no actual source CSV could be downloaded in the development environment. Run the importer with the real source file to populate it. Do not describe an unpopulated import as completed.

## Relationship to the recipe recommender

The original `app.py` still uses its own `RECIPE_DATA_DIR` dataset. This import does **not** replace recipe ingredients with supermarket SKUs, nor does it overwrite the existing ingredient price catalog: branded packs, units, size variants and recipe ingredients require an explicit reviewed mapping before reliable per-recipe pricing.

A BigBasket product listing does not contain `stock_qty`, `required_qty`, `unit_cost`, `expiry_date`, or sales transactions. The seller markdown engine therefore cannot be validated on actual BigBasket inventory using this dataset alone. Do not fill missing retailer fields with fake values labelled real.

## DSF experiments to add once the original datasets are present

- Catalog data quality: invalid prices, missing ratings, pack parseability, category distribution.
- Product-level historical pricing analysis: discounts vs MRP, brand/category variance, price-per-100g comparability.
- Recipe-to-product matching: reviewed matches and coverage/precision metrics; ambiguous matches stay unmatched.
- Separate Instacart experiment: association rules (support, confidence, lift) with a temporal customer-level evaluation.
- Seller decision comparison: synthetic inventory urgency baseline vs heuristic changes; no real sales uplift claims without outcomes.
