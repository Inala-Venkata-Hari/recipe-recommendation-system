# Learned inventory-risk score

The seller algorithm selector in `usda_trial.py` offers the existing rule-based
baseline and an ML risk model. The default is the ML experiment. Switching methods
can change prices, so affected promotions must be republished by the seller.

## What is learned

A regularized fractional logistic regression learns coefficients by minimizing
cross-entropy between observed unsold fraction and predicted unsold fraction.
Training uses Newton/IRLS updates, an intercept, standardized input features, and
L2 regularization (0.5; a fixed, untuned hyperparameter). Fractional labels are in
[0,1]. Inference returns sigmoid(intercept + standardized features × coefficients).

Features: log stock, log average daily sales, forecast horizon (up to seven days),
age divided by target holding period, recipe frequency ratio, and missing-data
indicators. The target is the fraction of initial stock left after the forecast
horizon, at an unchanged price. Missing expiry assumes a seven-day horizon.

The model prediction replaces `discount_priority` and `urgency_score` in ML mode.
The old rule priority is retained in `rule_priority` for comparison. Frequency
is a model input rather than a manually applied multiplier in ML mode.
Eligibility checks, expiry exclusion, seller discount maximum, average combo
priority, and minimum margin remain explicit business rules. Therefore this is
**ML-assisted markdown prioritization**, not a learned optimal pricing policy.

## Training provenance

The bundled model is trained on **simulated sales outcomes**, not real retailer
history and not labels copied from the current heuristic. The generator samples
product-level demand and batch conditions; future sales are Poisson outcomes
from an explicit assumed demand/freshness process. Observed recent sales are noisy.
Simulated unsold fraction is calculated from stock minus simulated future sales.
This simulator still encodes manually chosen assumptions: ML learns the simulator's
relationships, which are not evidence of real customer behavior.

180 products × 60 episodes = 10,800 records. Products are split without overlap:
126 training, 27 validation, 27 test (7,560 / 1,620 / 1,620 rows). Neither product IDs
nor future sales are input features. This is a product-held-out test, **not a temporal
real-world evaluation**. There is no tuning on the test split. Reported MAE/RMSE
compare against a constant training-mean prediction; the rule score is available
for display but is not treated as an empirically calibrated forecast.

Test MAE: about 0.086; constant-average baseline MAE: about 0.297. These are fractions,
so 0.086 means 8.6 percentage points of stock. MAE is not accuracy. No business uplift,
causal discount response, probability calibration guarantee or real-world efficacy
is claimed. The model does not learn which discount causes a product to sell.

## Reproduce offline

```bash
python train_inventory_model.py
python -m unittest discover -s tests -p test_ml_inventory.py
streamlit run usda_trial.py --server.port 8503
```

All training and inference use already-installed NumPy; no scikit-learn, downloads,
remote inference or API key is required. Model parameters, feature order, seed,
training provenance, split and held-out metrics are saved in
`models/inventory_risk.json`. The seller evaluation panel displays these values
and the standardized learned coefficients. Coefficients are neither importance
percentages nor causal effects.

Before operational use, collect batch snapshots and later sales outcomes over a
fixed, recorded horizon, including prices and promotions. Validate chronologically
and by product/store, assess calibration and compare the rule policy on actual
outcomes. Learning price elasticity or choosing an optimal discount requires
additional price-response data and suitable evaluation, beyond this risk model.
