# Verified replacement grocery price source

Selected source: [BigBasket Products — Chinmay Shanbhag](https://www.kaggle.com/datasets/chinmayshanbhag/big-basket-products), dataset version 1, publisher last updated 2022-08-21.

Downloaded and inspected the actual BigBasket.csv on 2026-11-08. It contains **8,208 rows** and explicit ProductName, Brand, Price, DiscountPrice, Quantity, Category, SubCategory and Absolute_Url fields. This is the full file corresponding to the 8,208-row dataset advertised by the notebook-only GitHub repository examined earlier.

**1,761 food listings** have a positive observed DiscountPrice and an unambiguous single gram/kilogram quantity. Locally exported as data/external/price_candidates/chinmayshanbhag/unit_priced_food_products.csv. Source metadata and hash are recorded beside it. Files remain ignored by Git; reuse licensing has not been established from the inspected API metadata.

Observed examples: onion 2 kg at INR52 -> INR2.60/100g; potato 1 kg at INR38.75 -> INR3.875/100g; whole-wheat atta 2 kg at INR118 -> INR5.90/100g. These are historical listed prices, not live quotes. Volume and piece-based packs are excluded rather than converted to grams by assumption.

This source resolves the previous missing-quantity problem. It is now integrated into the active filtered profile using source URLs and explicit ingredient mappings. After product-context and source-quality checks, 75 ingredient names have unit prices and 6 complete recipes remain. See BIG_DATA_README.md for reproduction and filtering details. Do not infer retailer costs, dates or calorie values from these price records. Do not represent a historical source as current retailer stock.

Official supplementary source: [Department of Consumer Affairs Price Monitoring System](https://fcainfoweb.nic.in/Default.aspx) supplies explicitly unit-labelled retail commodity averages, but those are market benchmarks rather than BigBasket SKU prices. Keep the two sources separate unless the user authorizes combining them.
