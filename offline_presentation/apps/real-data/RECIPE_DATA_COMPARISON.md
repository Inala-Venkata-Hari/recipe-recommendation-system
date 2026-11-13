# Recipe dataset decision — 2026-11-08

Both full public CSVs were downloaded and inspected locally. No recipe texts are committed by this change.

| Criterion | Anupam007/indian-recipe-dataset | datahiveai/recipes-with-nutrition |
|---|---|---|
| Actual source records | 5,938 | 39,447 |
| Structured ingredient names | Cleaned comma-separated text | JSON ingredient objects |
| Structured gram weights | Absent; quantities in free text | 350,029 / 352,596 ingredient entries have positive weights |
| Recipes with all positive ingredient weights | Cannot establish without parsing/inference | 37,503 |
| Recorded servings | No structured field | Available |
| Cooking time | Present; 2 nonpositive values | Absent |
| Regional coverage | Strong Indian focus | Global; 915 source records tagged Indian |
| Source URLs | Present | Present |
| Publisher-declared license | No dataset card/license found in inspected HF metadata | CC BY-NC 4.0 |

## Decision

Use DataHive as the default real recipe profile because structured weights and servings best support missing-item cart quantities and recipe pricing. Indian recipes remain a useful future regional supplement, but require quantity parsing, ambiguous-unit handling and licensing clarification. This is a structural usefulness decision, not a claim that DataHive recipes are newer or nutritionally validated.

Source: https://huggingface.co/datasets/datahiveai/recipes-with-nutrition at revision 33ff70ba3dc1a1a77395fc477934b4ffb18a347d. Indian comparison source: https://huggingface.co/datasets/Anupam007/indian-recipe-dataset at revision 12a8cda64780a28337525ba73b3ffc2881edbe35.

## Imported profile

`data/real_recipes/` contains 39,447 unique source-URL recipes and 5,613 normalized ingredient names. Duplicate ingredient entries are combined by summing source weights only when all repeated entries have valid weights. Missing or zero weights remain unknown. Publisher gram weights can be estimates; they are not independent measurements.

The app defaults to this profile when imported files exist. The sidebar can switch to the unchanged synthetic presentation demo or Food.com sample. RECIPE_DATA_DIR remains an explicit override. Profile changes clear cart/selected bundles so they cannot leak between datasets. Recipe results are paginated, and caches are keyed by data path/modification time and catalog content.

No cooking time is fabricated. Source calorie values are retained as source_calories but are not shown as calories_per_serving: the source field basis has not been independently resolved, and the dataset card's nutrient wording alone does not establish it. Time/calorie sorting therefore uses the existing count-based fallbacks when these values are unavailable. Busy/late-work schedule matching cannot be inferred without cooking times. Family matching uses recorded servings.

Catalog prices are initially blank. The recipe dataset supplies no INR prices, and the BigBasket importer has no approved SKU-to-ingredient mapping yet. No synthetic prices, nutrition or inventory are copied into this profile. Recipe costs become available only after quantities and all corresponding catalog rates are known. Seller batches must be supplied separately.

## Reproduce

From this branch, run `python import_real_recipes.py --download`. This downloads the pinned 449,782,831-byte publisher CSV and builds the profile; internet access is required only for download. Existing real-profile seller prices and inventory are preserved on reimport. Run `streamlit run app.py` and choose the dataset in the sidebar.

License: DataHive declares CC BY-NC 4.0. Preserve attribution and underlying recipe source URLs; this integration is for noncommercial educational use. Raw and generated datasets are ignored by Git; manifests retain source URL, revision and SHA-256 checksum locally. This code does not provide permission for commercial use.
