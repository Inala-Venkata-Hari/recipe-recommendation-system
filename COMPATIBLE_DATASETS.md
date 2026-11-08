# Verified compatible pair — USDA 2017–2018

## Recommendation

Prioritize compatibility over country: use **FNDDS 2017–2018** (food descriptions, nutrient values, portions and ingredient formulations) together with **Purchase-to-Plate National Average Prices 2017–2018** (estimated USD per 100 edible grams).

- Nutrition/food source: https://fdc.nal.usda.gov/download-datasets/ — historical FNDDS 2017–2018 JSON.
- Price source: https://www.ers.usda.gov/data-products/purchase-to-plate — public PP-NAP CSV ZIP.
- Documentation: https://www.ars.usda.gov/ARSUserFiles/80400530/pdf/fndds/2017_2018_FNDDS_Doc.pdf.

Both source archives were downloaded and checked locally, rather than relying on descriptions. FNDDS has 7,083 foods. The price CSV contains 15,012 records across four periods; select the 4,435 records for 2017/2018. Modification codes apply to the 2011/2012 series only, so do not filter 2017/2018 on mod_code=0 (that column is blank for this period).

## Verified compatibility

Join price food_code to FNDDS foodCode. All **4,435 price records match exactly**, without fuzzy ingredient matching. All have positive prices and energy values in kcal per 100 g. Preserve the period and currency. USDA price construction includes imputed values and prepared-food formulations; these are national-average estimates, not observed current SKU prices.

For ingredient-driven recommendations, 75 multi-ingredient formulations have exclusively priced FNDDS ingredient codes and positive ingredient gram weights. This is a separate coverage measure: **4,435 matched food prices do not mean 4,435 fully ingredient-priceable recipes**. Other formulations reference SR/NDB ingredient codes that are not direct keys in the public price table. USDA's full Purchase-to-Plate ingredient/crosswalk tools are restricted; the public files must not be described as providing them.

The source contains standardized food formulations, not ordinary home recipe cards. No cooking instructions or times should be invented. Nutrient values use a declared 100 g basis, and portions can be scaled using reported gram weights. Input recipe weights and edible yield/moisture must be interpreted before costing whole prepared portions. Historical national averages cannot demonstrate actual retailer stock, costs, expiry or realized sales uplift.

## Local evidence

`data/external/usda_pair/compatibility_report.json` records counts, source URLs and ZIP checksums. `matched_food_prices_nutrition_2017_2018.csv` holds the exact joined food table. `directly_priced_formulations.csv` holds the 75 formulation candidates. These local source/research files are excluded from Git. The active app has not been replaced during this research.

## Other evaluated candidates

A 25,768-row INR grocery file has explicit quantities but requires audited ingredient matching. Tesco's recipe file contains 3,597 recipes and 30,441 ingredient rows but free-text units. An Indian recipe/Sydney grocery pair contains 149 recipes and 5,693 product records, but mixes household recipe units and AUD prices; the publisher's INR conversion is not an Indian retail observation. Palate's 250-record structured sample exposes clear macro bases but inspected records contain questionable ingredient normalization (garlic powder mapped to garlic, file powder mapped to baking powder); it is not preferable merely because its fields are convenient.
