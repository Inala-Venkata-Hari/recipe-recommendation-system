# Smart Cart — full USDA demonstration workflow

## Run

```bash
python build_usda_trial.py --download
streamlit run usda_trial.py --server.port 8503
```

This is a separate full-workflow experiment. The original `app.py` and its BigBasket/synthetic profiles are preserved. Source prices, calories and food identifiers stay in USD/FNDDS 2017–2018. Derived data live in ignored `data/usda_trial/`; seller data are separate under `data/usda_trial/workspace/`. Set USDA_DATA_DIR and/or USDA_WORK_DIR to isolate a copy.

## Five-minute demonstration

1. Open **Seller inventory & offers**. Assessment date defaults to 2026-11-08 for a reproducible scenario.
2. Expand **Load a clearly labeled demonstration inventory**, choose **Black beans with meat**, and click **Load simulated example batches**. This adds three simulated batches: 50 packs of 100 g, acquisition cost 60% of catalog rate, receipt eight days earlier and expiry two days later. These are scenario inputs, not observed USDA inventory. Duplicate demo IDs are preserved rather than overwritten.
3. Keep maximum discount 30%, minimum margin 5%, combo size 2. Inspect exclusions, effective cash discounts, profit and margin. Three pair offers should be available. Tick **Select all draft offers for publishing**, then **Publish selected offers**. End dates are exclusive and capped at batch expiry.
4. Open **Customer recommendations**. Select only the Black beans component from the catalog (or search formulations for Black beans with meat). Click that formulation’s **Add missing items to cart**. The missing beef/ham components are added at source quantities and the highest-saving non-overlapping published bundle is applied.
5. Scroll to checkout. Inspect regular USD total, applied savings and final total. Confirm simulated checkout, preview/download the HTML invoice, and open it in a browser to **Print / Save as PDF**.
6. Pause the applied offer in the seller tab. The existing cart must now reject that discount until it is removed or replaced. No stale invoice or checkout confirmation should remain.
7. Reset USDA trial to clear cart, selected combos, receipt and controls. Saved seller inventory, prices, publications and custom meals remain. No payment is taken and no stock is reserved or deducted.

## Seller functionality

- Create batches from the USD catalog, entering actual cost, stock, receipts, expiry and sales separately.
- Upload inventory CSV and reject unknown codes, invalid values or duplicate batch IDs. Expired/zero-stock rows remain visible as excluded decisions.
- Edit existing batch stock, cost and dates. Identity and stored original price snapshots remain fixed. New draft calculations use current catalog rates; changed economics or eligibility can invalidate published offers.
- Use existing age/expiry/excess scoring and frequency multipliers. Frequency is computed from the current formulation/meal corpus; it is not customer demand.
- Bound proposals to the 12 highest-priority distinct eligible foods, after selecting earliest expiry per food. This prevents enumerating all combinations across the 4,435-food catalog. The omitted count is visible.
- Publish/pause offers and export decision/history CSVs. Logs are local demo activity, not authenticated seller audits.
- Maintain USD seller price overrides separately from read-only USDA reference prices. Upload a CSV or edit one price. Existing batch records retain their price snapshot; draft/checkout economics use current catalog rates. Old published quotes must be republished when their cash price changes.

## Customer functionality

- Exact-code selections, matched-item counts and matched cart cost.
- Ranking always uses most selected components, then fewest additional items. Budget and calorie preferences break ties afterward. Budget can compare cost per 100 g input so different batch sizes do not misleadingly determine economy.
- Browse only published offers; search, sort, page and optionally prioritize schedule matches.
- Add missing components with recorded weights, automatically maximize total savings across non-overlapping published bundles, and apply one discounted 100 g unit per component. Remaining grams use catalog rates.
- Checkout revalidates publication, stock, expiry, current draft prices, margin policy and quantities. A component cannot be discounted twice. Invoice cash savings use the same rounded standalone line prices as checkout; cent rounding cannot exceed the configured discount cap.
- Create user-entered component meals using known codes, weights and optional menu context. These are not official USDA formulations. Their nutrition is a labeled component-weighted input estimate and excludes cooking changes.

## Schedule context

Busy/short break uses seller-declared minutes <=30; late study/work uses <=20; family uses seller-declared servings >=2. Missing times or servings are not inferred. After workout highlights protein >=10 g/100 g from the USDA record or a labeled user-meal input estimate; it is a display preference, not nutritional advice. Seller-entered menu context is separately labeled. Schedule matching does not change prices, publication, or the ingredient-count ranking.

## Data interpretation

FNDDS has 7,083 foods; 4,435 codes have a positive PP-NAP 2017/2018 price and energy value. Seventy-five multi-component formulations have prices for all components and positive gram weights. SR/NDB ingredient codes without direct public price matches remain excluded. Many components are already cooked or packaged; some survey formulations are statistical composites rather than literal recipes.

USDA prices are historical national-average estimates and include imputation. Calories are per 100 edible grams of final food. Ingredient input weight is not a final cooked yield or serving count. Retailer procurement costs, real stock, expiry, cooking times, realized demand and payments are not supplied by these data. The explicit demo generator must never be presented as observed stock. Generic corporate payment/authentication or real ordering integrations are not included.

## Verification

`python -m unittest discover -s tests` checks backward-compatible INR checkout plus USD prices, invoices, custom meals, inventory edits, candidate limits, publication/pause, and the end-to-end workflow. UI trials use temporary workspaces so they do not alter the real demonstration state.

Retail pack pricing: in **Catalog → Retail pack sizes**, save a seller-entered pack
weight and optionally its whole-pack selling price. For example, 500 g at $3.49
normalizes to $0.698 per 100 g for recipe costing, while checkout buys a whole
500 g pack for $3.49 when 120 g is needed. The shopping breakdown shows 380 g
left after use and identifies the price basis. Leaving pack price blank retains
the current catalog rate. Historical source prices are never overwritten.
Inventory and offers support recorded pack weights. Configure the catalog pack size,
create matching inventory batches (cost and stock are per pack), and publish fresh
offers. Existing batches keep their original unit; incompatible offers stay hidden.


Checkout validates the entire purchased quantity for inventory-tracked products,
excluding expired, future-received and incompatible pack batches. Catalog-only
products have unverified availability, explicitly identified in checkout; they do
not acquire invented inventory. No stock is reserved or deducted in this demo.
Invoices consolidate products and label the quantity covered by each combo;
additional packs remain at regular price. Cake and ice cream default to snacks,
with seller overrides retained.


Inflation adjustment is enabled by default in the sidebar. A pinned BLS US CPI-U
all-items, not seasonally adjusted snapshot (September 2026 index 336.940,
verified 2026-11-08) is divided by the mean of 2017 and 2018 annual indexes
(245.120 and 251.107). The approximate factor is 1.358, not the latest one-year
inflation rate. This is a broad purchasing-power estimate, not a grocery-specific
price forecast or live quote. The two-year source period is approximated with an
equally weighted index mean. Original source data and seller-entered prices/costs
are preserved. Current estimates feed recipe costs, pack checkout and new offer
quotes; changed publications require seller review and republishing. The snapshot
is not automatically refreshed; its observation and verification dates are shown.
Sources: https://www.bls.gov/news.release/archives/cpi_10142026.htm and
https://www.bls.gov/regions/mid-atlantic/data/consumerpriceindexannualandsemiannual_table.htm
