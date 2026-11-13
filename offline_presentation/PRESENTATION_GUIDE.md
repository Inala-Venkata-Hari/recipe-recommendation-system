# Offline presentation — 12 November 2026

## Start on this laptop

All data and Python packages needed by these demos are already local. No GitHub,
API calls, dataset imports, package installations or internet connection are needed.

```bash
cd /home/hari/Desktop/College/DataScienece/Assignment/Project/offline_presentation
./START_DEMOS.sh
```

Open `index.html` in your browser. The three direct addresses are:

| Demo | URL | Role |
|---|---|---|
| Original (`main`) | http://localhost:8601 | Recipe matching baseline |
| Synthetic (`small-test`) | http://localhost:8602 | Controlled end-to-end workflow |
| Real reference data (`small-test-big-data`) | http://localhost:8603 | Larger catalog, realistic unit handling and data provenance |

Open `presentation.html` for the updated standalone slide deck, or use the included
9-page `presentation.pdf` directly in a PDF viewer. Use left/right
arrow keys; F11 enables browser fullscreen. Browser Print can save all slides as PDF.
`slides.html` preserves the earlier project deck as an additional fallback.

Before speaking: open each demo once, keep the tabs open, plug in the laptop,
disable sleep temporarily, and test the projector. Internet/Wi-Fi can be off.
These addresses run on this laptop; another device cannot reach `localhost` here.

## Suggested 8–10 minute walkthrough

### 1. Original recommendation baseline (2 minutes)

Open port 8601. Add **butter, brown sugar, egg, unsweetened applesauce, cinnamon**.
These inputs were tested against the bundled original dataset. Show the selected
item count, matching recipes and the preference options. Explain that this version
starts with recipe matching. Its budget option explicitly lacks reliable prices;
do not claim checkout or seller inventory exists in this original baseline.

### 2. Synthetic controlled experiment (3 minutes)

Open port 8602. This snapshot is forced to the synthetic dataset: **15 recipes,
28 ingredient catalog entries, synthetic inventory and prices**. All are fictional.
Keep the **5 November 2026 assessment date**: this is a historical scenario and
makes near-expiry examples reproducible. It is not today's real stock.

1. Select **rice, tomato, onion** in the cart. Explain match-first sorting and
   additional ingredients. Household pantry items may already be excluded.
2. Expand **Browse published combo offers**. There are **20 prepared offers**.
   Add an enabled published combo. Its actual pack quantities enter the cart.
3. In simulated checkout, confirm checkout and preview the printable HTML invoice.
   Download it if useful, then print/save PDF through the browser.
4. Open the seller tab: show stock age, expiry, excess-stock scores, margin limit,
   draft vs published offers. Changing settings can invalidate existing quotes;
   reset the demo if you do not want to republish on stage.

### 3. Real-data integration (3 minutes)

Open port 8603. Explain **4,435 exactly linked price-and-calorie food codes** and
**75 fully component-priced USDA formulations**. The price source is historical
USDA Purchase-to-Plate; nutrition/formulations come from USDA FNDDS. Some components
are already cooked or packaged. These are survey formulations, not all literal
raw-ingredient cooking recipes.

1. Search/select **Rice, brown, cooked, no added fat**. Find **Beans and brown rice**.
2. Show additional components, one-serving ingredient weights and estimated costs.
3. Click **Add missing items to cart**. A useful published combo applies
   automatically. There are **6 prepared offers** from **7 simulated batches**.
4. Show needed grams, whole packs bought, leftovers and one invoice row per product.
5. Confirm checkout. Explain the separate discounted quantity on each invoice row.
6. Show seller inventory and catalog pack-size/price settings if time permits.

This presentation copy uses **12 November 2026** as the real-data assessment date.
Stock, acquisition costs, age, sales and expiry in its preloaded batches are
**simulated**; USDA does not supply retailer stock records. Prepared batches expire
14 November, exclusive. Keep the pinned assessment date for later rehearsals.

CPI adjustment uses a **pinned September 2026 snapshot verified 8 November**.
It is an approximate historical-price adjustment, not today's live grocery quote.
Seller-entered prices stay separate. Source links need internet; do not click them
during the offline demonstration. The necessary source notes are bundled locally.

## Explain the algorithm

- Normalize ingredients and match selected ingredient identities to formulations.
- Rank by more cart ingredients used, then fewer additional items, then preference.
- Inventory urgency: **35% age + 40% expiry + 25% excess-stock risk**; unavailable
  signals are omitted and weights renormalized.
- Apply corpus-frequency multipliers from **1.0 to 1.3**. Recipe coverage is not
  measured customer demand.
- Cap discounts by seller maximum and minimum margin; expired batches are excluded.
- Auto-select non-overlapping eligible combos for maximum total savings.
- Check full purchased quantities for inventory-tracked products. Catalog-only
  availability is unverified. Checkout is simulated; no payment or stock deduction.

Do not claim a trained demand-forecasting model or measured waste reduction.
The system demonstrates an interpretable recommendation and markdown policy.

## Reset / recovery

To remove all on-stage demo edits and restore the prepared offers:

```bash
./RESET_DEMOS.sh
./START_DEMOS.sh
```

Reload the browser tabs after restarting. These scripts affect **only the isolated
presentation copies**; original branches and normal seller workspaces are preserved.
The in-app Reset/Clear cart buttons do not restore seller publications and inventory.

Stop the servers: `./STOP_DEMOS.sh`.
Check readiness: run the existing Python interpreter with `manage.py status`.
Logs: `logs/original.log`, `logs/synthetic.log`, `logs/real-data.log`.
If a port is in use, the launcher stops with an explanation rather than killing an
unrelated process. Use the ports above, not older 850x tabs from development.

## Verification and backup

All three workflows were exercised using Streamlit AppTest with outbound Python
socket connections blocked. Tests covered recipe selection, existing offers,
automatic discounts in the real-data app, combo checkout and HTML invoice generation.
See `checks/*.json`. Sample invoices are also saved under `sample-invoices/`
for a static fallback if a live demo is interrupted. Local HTTP readiness is checked separately by the launcher.
Browser/projector appearance still needs a quick visual check on your display.

`manifest.json` records the branch commit used for each snapshot. The presentation
snapshot changes only the real-data default scenario date and adds isolated seed
workspaces. No branch checkout is needed to switch demos.

A ZIP backup is supplied beside this folder. It includes app code, prepared data,
seed workspaces, slides, scripts and this guide. It excludes logs and running PID
state. It does **not** include the Python interpreter or installed dependencies.
On this laptop the existing environment is used. On another machine install the
packages from `requirements-environment.txt` before going offline, then set
`PRESENTATION_PYTHON` to that environment's Python. The ZIP alone is not an offline
Python installer and Linux shell launchers require a compatible shell.


## ML experiment added

The real-data seller tab now defaults to **ML: learned unsold-stock risk**. The
rule-based baseline remains selectable. Open the ML evaluation panel to show
learned coefficients and the product-held-out synthetic test metrics (8.6 percentage
point MAE vs 29.7 for the constant-average baseline). Training uses 10,800 simulated
batch outcomes; 7,560 train, 1,620 validation, 1,620 test. No real demand model or
causal discount response is claimed. The prediction replaces manual risk weights;
margin constraints and the mapping from risk to discount remain business rules.
Changing scorer invalidates changed quotes: publish the current drafts again.
The synthetic demo remains the original rule-based baseline. See real-data/ML_MODEL.md
inside the application snapshot for the full experiment description.

## Transfer version

This folder is now included in the GitHub `small-test-big-data` branch. On a new
laptop, run `python setup_presentation.py` once with internet, then
`python manage.py start`. It uses its own local `.venv`; paths to the old laptop
are not needed. Prepared real-data offers now use the ML scorer by default. The
fixed scenario dates are retained so the demonstration stays reproducible. See
`../NEW_LAPTOP.md` for Windows/Linux/macOS setup instructions.
