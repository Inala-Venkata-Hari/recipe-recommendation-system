# Presentation walkthrough

This is an explainable markdown recommendation prototype, not a trained demand model. The demo is synthetic; prices, sales rates, expiry assumptions and nutrition are illustrative. No sales uplift or waste reduction has been measured.

## Dataset

Use the bundled `data/synthetic_demo` snapshot, assessed on **2026-11-05**. It contains 15 recipes, 28 catalog/classification entries, and 12 inventory batches. Each stock unit is a **100 g pack**. Inventory unit prices match catalog prices per 100 g; costs are simulated fractions of those prices. Recipe quantities support actual cost calculations. Frequency categories are calculated from the 15 recipes. This small sample cannot demonstrate the Rare category (<3%), since even one occurrence is 6.67%; rare-category behavior is covered by automated tests.

The regular Food.com-derived 5,000-recipe dataset remains in `data/`. It lacks batch dates, transaction demand and ingredient quantities needed for this presentation's inventory economics. The synthetic data fills these fields explicitly rather than representing invented values as observations.

## Five-minute demonstration

1. Open http://127.0.0.1:8502. Point out the synthetic-data banner.
2. In the customer tab select rice, tomato and onion; show recipes, quantities and budget sorting.
3. Open Seller inventory & combo offers. Keep assessment date 2026-11-05. Set maximum discount to 30%, minimum margin to 15%, and both combo-size controls to 2.
4. Expand classification parameters. Explain that category multipliers (1.0–1.3) adjust urgency; recipe frequency is versatility, not sales demand.
5. Show excluded batches: cream expired, cucumber has zero stock, lentils has no markdown urgency.
6. Inspect paneer/tomato urgency versus fresh rice. The low-margin chicken demonstrates the margin cap; a mixed combo may still be eligible because the margin floor applies to the whole bundle.
7. Show original price, offer price, cost, profit, margin, quantities and reason breakdown. Expand an offer to show recipes using its ingredients.
8. Download the CSV. Explain each row is an alternative offer: stock overlaps, so profits cannot be summed across all rows.
9. Optionally upload the three `discount_test*.csv` files from the parent workspace. Their earlier expected discounts apply to the API without classifications; in the app the active classification multipliers also apply.

## What to say about results

The system produces reproducible, margin-constrained offers and excludes unusable stock. It does not predict purchases or allocate stock across offers. Evaluate future effectiveness using transaction-level sell-through, waste and gross profit against the previous surplus-only baseline.

## Reproduce

Run `python generate_synthetic_data.py` to regenerate the fixed snapshot. This rewrites the demo CSVs, including demo pantry files; use a separate data directory for your own edits. Run `python -m unittest discover -s tests` to validate behavior.
