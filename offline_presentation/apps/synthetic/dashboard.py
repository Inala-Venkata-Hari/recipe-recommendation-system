"""Read-only analytics dashboard for Smart Cart's data and algorithms.

Run: streamlit run dashboard.py
Reads the same dataset selection as app.py. Does not alter application CSV files.
"""
import ast
import os
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
SYNTH = ROOT / "data" / "synthetic_demo"
DATA = Path(os.getenv("RECIPE_DATA_DIR", str(SYNTH if (SYNTH / "recipes_cleaned.csv").exists() else ROOT / "data")))

st.set_page_config(page_title="Smart Cart — DSF Analytics", page_icon="📊", layout="wide")
st.title("📊 Smart Cart | Data Science & Techniques Dashboard")
st.caption(f"Read-only demonstration • Dataset: {DATA} • Values and results reflect the loaded files.")

def read(name):
    p = DATA / name
    if not p.exists() or p.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(p)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        st.warning(f"Could not read {name}: {exc}")
        return pd.DataFrame()

def parse_list(v):
    if isinstance(v, list):
        return v
    if not isinstance(v, str):
        return []
    try:
        x = ast.literal_eval(v)
        return x if isinstance(x, list) else []
    except (ValueError, SyntaxError):
        return []

recipes = read("recipes_cleaned.csv")
classified = read("ingredients_classified.csv")
catalog = read("ingredient_catalog.csv")
inventory = read("seller_inventory.csv")
if not recipes.empty and "ingredients" in recipes:
    recipes["parsed_ingredients"] = recipes["ingredients"].map(parse_list)
    recipes["ingredient_count_derived"] = recipes["parsed_ingredients"].map(len)

pages = st.tabs(["Overview", "Data handling", "Ingredient analytics", "Recommendation techniques", "Seller & discounts", "Validation & limitations"])

with pages[0]:
    st.subheader("Dataset snapshot")
    metrics = [
        ("Recipes", len(recipes)),
        ("Unique ingredients", len(classified) if not classified.empty else len({x for row in recipes.get("parsed_ingredients", []) for x in row})),
        ("Catalog items", len(catalog)),
        ("Inventory batches", len(inventory)),
    ]
    for col, (label, value) in zip(st.columns(4), metrics):
        col.metric(label, f"{value:,}")
    st.markdown("**Data sources:** cleaned recipe records, ingredient classification, per-ingredient catalog, and seller inventory.")
    st.info("The synthetic demo contains fictional prices and nutrition. Dashboard statistics are descriptive, not measured sales or model accuracy.")
    if not recipes.empty:
        st.dataframe(recipes[[c for c in ["name", "n_ingredients", "minutes", "calories_per_serving"] if c in recipes]].head(30), use_container_width=True)

with pages[1]:
    st.subheader("Data handling workflow")
    for stage, detail in [
        ("1. Load & select", "Read source CSV, require id/name/ingredients, retain relevant columns."),
        ("2. Clean", "Drop missing essential fields and duplicate recipe IDs; safely parse list-like strings."),
        ("3. Normalize", "Canonicalize ingredient names; remove duplicate ingredients within each recipe."),
        ("4. Filter", "Keep recipes with at least five ingredients and positive, numeric cook time. The standard preprocessing sample is capped at 5,000 recipes with a fixed seed."),
        ("5. Engineer features", "Derive ingredient counts, calories per serving, frequency ratio, distinctiveness score, and ingredient categories."),
        ("6. Enrich", "Merge normalized names with catalog prices, nutrition reference values and inventory data. Keep missing values explicit."),
    ]:
        with st.expander(stage, expanded=stage.startswith("1.")):
            st.write(detail)
    if not recipes.empty:
        missing = recipes.drop(columns=["parsed_ingredients"], errors="ignore").isna().sum().sort_values(ascending=False)
        st.markdown("**Missing values in loaded recipe data**")
        st.bar_chart(missing.head(15))
        if "minutes" in recipes:
            durations = pd.to_numeric(recipes["minutes"], errors="coerce").dropna()
            if not durations.empty:
                st.markdown("**Cooking-time distribution**")
                st.bar_chart(durations.clip(upper=180).round(-1).value_counts().sort_index().rename("recipes"))
        st.metric("Duplicate recipe IDs in loaded file", int(recipes["id"].duplicated().sum()) if "id" in recipes else "Unavailable")
    else:
        st.warning("No recipe CSV found. Run python generate_synthetic_data.py or python preprocess.py.")

with pages[2]:
    st.subheader("Ingredient frequency classification")
    st.latex(r"f(i)=\\sum_{r\\in R}\\mathbf{1}[i\\in r],\\quad p(i)=\\frac{f(i)}{|R|}")
    st.latex(r"d(i)=\\ln\\left(\\frac{|R|+1}{f(i)+1}\\right)")
    st.caption("Category thresholds: Common ≥25%; Moderately common ≥10%; Specialized ≥3%; otherwise Rare / recipe-specific.")
    if not classified.empty:
        if "ingredient_frequency_category" in classified:
            st.bar_chart(classified["ingredient_frequency_category"].value_counts().rename("ingredients"))
        if {"ingredient_name", "recipe_frequency"}.issubset(classified.columns):
            top = classified.nlargest(15, "recipe_frequency").set_index("ingredient_name")["recipe_frequency"]
            st.markdown("**Top 15 ingredients by recipe frequency**")
            st.bar_chart(top)
        st.dataframe(classified, use_container_width=True, hide_index=True)
    else:
        st.info("Ingredient classification file is unavailable.")

with pages[3]:
    st.subheader("Recommendation logic — rule-based, not a trained classifier")
    st.markdown("""
**Candidate matching:** normalize the customer's cart, compare it with each recipe's ingredient set, then identify matched and additional ingredients.

**Ranking methods:**
- **Calories:** ascending calories; tie-break by fewer additional items, then shorter time.
- **Time Taken:** ascending cook time; tie-break by fewer additional items, reliable lower cost, then calories.
- **Budget Friendly:** ascending *reliable* recipe cost; tie-break by fewer additional items, then shorter time.
- Highlight recipes needing zero additional ingredients. At least three cart ingredients are required by the customer UI.

**Schedule awareness:** predefined context rules prioritize relevant meals. This does not infer the customer's mood.
""")
    st.latex(r"\\mathrm{missing}(r,C)=|I_r\\setminus(C\\cup P)|")
    st.caption("Iᵣ = recipe ingredients; C = cart ingredients; P = approved pantry staples.")
    if not recipes.empty:
        choices = sorted({str(x) for row in recipes["parsed_ingredients"] for x in row})
        picked = st.multiselect("Try ingredient-set matching", choices, default=choices[:min(3, len(choices))])
        cart = set(picked)
        if picked:
            examples = []
            for row in recipes.itertuples():
                ingredients = set(row.parsed_ingredients)
                overlap = len(ingredients & cart)
                if overlap:
                    examples.append({"Recipe": getattr(row, "name", ""), "Matched": overlap, "Additional": len(ingredients - cart)})
            if examples:
                st.dataframe(pd.DataFrame(examples).sort_values(["Matched", "Additional"], ascending=[False, True]).head(15), hide_index=True, use_container_width=True)

with pages[4]:
    st.subheader("Seller inventory and markdown policy")
    st.markdown("""
**Batch urgency:** weighted signals for stock age (35%), expiry risk (40%) and expected unsold proportion (25%), with available weights renormalized if optional signals are missing.

**Frequency multiplier:** Common ×1.0, Moderately common ×1.1, Specialized ×1.2, Rare ×1.3. These are heuristics, not ML-learned coefficients.

**Combo pricing:** generate eligible 2–4 ingredient bundles; derive a discount from average priority, enforce a minimum gross-margin floor, and show estimated profit and savings.

**Publishing & checkout:** only valid, active published promotions reach customer checkout; the prototype simulates receipts without making payments or deducting actual stock.
""")
    if not inventory.empty:
        fields = [c for c in ["ingredient_name", "batch_id", "stock_qty", "required_qty", "unit_cost", "unit_price", "received_date", "expiry_date"] if c in inventory]
        st.dataframe(inventory[fields], use_container_width=True, hide_index=True)
        for column in ["stock_qty", "required_qty"]:
            if column in inventory:
                st.metric(f"Total {column.replace('_', ' ')} (source units)", f"{pd.to_numeric(inventory[column], errors='coerce').sum():,.1f}")
        st.caption("Batch units may differ across records; totals should only be compared when units are consistent.")
    else:
        st.info("Inventory CSV unavailable.")
    st.markdown("**Catalog coverage**")
    if not catalog.empty:
        for field in ["price_per_100g", "kcal_per_100g"]:
            if field in catalog:
                known = pd.to_numeric(catalog[field], errors="coerce").notna().sum()
                st.progress(float(known / len(catalog)), text=f"{field}: {known}/{len(catalog)} populated")

with pages[5]:
    st.subheader("Evaluation and honest limitations")
    st.markdown("""
**Available checks:** missing-value counts, duplicates, normalization, frequency distribution, coverage of pricing and calories, recipe match count, and seller stock/margin eligibility.

**Recommended future experiments:** compare recipe coverage and recommendation quality with simple baselines; evaluate inventory waste, units sold and gross profit against the surplus-only discount policy; report results separately for synthetic and real data.

**Not currently justified:** claims of trained-model accuracy, precision/recall, inferred customer mood, improved sales, or optimized discount performance without real labels and measured experiments.
""")
    st.write("**Implementation files:** `preprocess.py`, `ingredient_normalization.py`, `recipe_matching.py`, `recipe_sorting.py`, `inventory_discounts.py`, `recipe_costs.py`, and `app.py`.")
