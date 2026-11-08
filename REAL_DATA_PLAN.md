# Real-data integration plan — small-test-big-data

## Verified starting point (2026-11-08)

Downloaded third-party processed BigBasket listing snapshot from https://raw.githubusercontent.com/arnavification/bigbasket_sql/main/data.csv.

- Source rows: 26,127; valid distinct listings after current importer: 26,117.
- 11 categories; 90 subcategories.
- 12,801 grocery candidates under the current heuristic (requires review).
- Only 139 listings have unambiguous explicit mass-based pack information; not all are food ingredients.
- Existing recipe files contain 5,000 Food.com-derived recipes and a separate 15-recipe synthetic demonstration.
- Raw and generated listing files remain local, ignored by Git; source manifest records URL and SHA-256 hash.

## Phase 1: trustworthy data and exploration

Keep raw data immutable. Add schema validation, finite/positive price checks, category exclusions, duplicate accounting and import reports. Preserve source product IDs and source provenance. Display imported counts, missingness and pack-size coverage. Verify nutrition definitions before displaying calories as per-serving estimates.

## Phase 2: ingredient-to-product mapping

Build a review table with recipe ingredient, source SKU, product name, match method, approval, pack mass and source price. Suggest exact normalized matches and explicit aliases first; fuzzy matches are candidates only. Distinguish rice from rice flour, milk from milk powder and fresh tomato from tomato sauce. Do not assume a product name uniquely identifies a SKU. Only approved matches with known mass produce INR/100g prices. Leave unknown weights unpriced; volume-to-mass conversion requires ingredient-specific density and is out of scope initially.

## Phase 3: main app integration

Add a selectable real-data profile rather than replacing the demo. Use the existing 5,000 real recipes first, recompute frequency categories on that recipe corpus and connect approved SKU mappings to catalog pricing. Ingredient frequency remains recipe coverage, not sales velocity. Show product/brand/pack/price provenance and missing price coverage. Recipe cost and invoice estimates require known ingredient quantities; existing Food.com ingredient-name lists cannot supply them. Keep estimates unavailable when quantities are missing instead of inventing weights.

## Phase 4: seller inventory

Use mapped catalog products to create seller-entered batches (stock unit, quantity, cost, receipts and expiry). Public listings do not contain observed stock, procurement cost, expiry or sales rate. Label scenario batches as simulated and actual manually supplied batches as seller-entered. Keep historical listed sale/MRP discounts separate from our urgency-based promotional discounts. Preserve margin checks, publication, pauses and checkout revalidation.

## Phase 5: expand and benchmark

After obtaining the full Food.com recipe source from its dataset publisher, process more than the current 5,000 rows and remove the sampling cap through an explicit importer option. Add ingredient-to-recipe inverted indices, cached loading and paginated results. Avoid enumerating every 2–4-item combination across thousands of inventory items: restrict candidates to urgent stock and recipe-compatible bundles and show any candidate limit. Measure query time and memory on increasing dataset sizes.

## Presentation evidence

Report actual imported/usable records, approved mapping coverage, per-100g price coverage, matching precision on a reviewed sample, response times and margin/exclusion checks. Do not claim live prices, measured demand, real waste reduction or proven sales uplift from a historical catalog snapshot. Keep unknown values visible. Raw source redistribution requires a verified license; provenance is not permission.

## Immediate next deliverable

A data-quality view and ingredient/SKU review workflow, followed by a real-data profile in the main app. Do not overwrite synthetic_demo or restore stashed small-test changes without reviewing compatibility.
