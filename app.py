import ast
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from ingredient_normalization import normalize_ingredient, normalize_ingredient_list
from recipe_matching import find_ranked_matches
from recipe_sorting import sort_recipes
from inventory_discounts import generate_combo_offers

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "recipes_cleaned.csv"
CLASSIFICATION_FILE = ROOT / "data" / "ingredients_classified.csv"
INVENTORY_FILE = ROOT / "data" / "seller_inventory.csv"
CATALOG_FILE = ROOT / "data" / "ingredient_catalog.csv"
PANTRY_FILE = ROOT / "data" / "pantry_ingredients.csv"
PANTRY_CANDIDATES_FILE = ROOT / "data" / "pantry_candidates.csv"
CUSTOM_FILE = ROOT / "data" / "custom_recipes.csv"


def parse_list(value):
    if isinstance(value, list):
        return value
    if pd.isna(value):
        return []
    try:
        parsed = ast.literal_eval(value)
        return parsed if isinstance(parsed, list) else []
    except (ValueError, SyntaxError, TypeError):
        return []


@st.cache_data
def load_recipes():
    df = pd.read_csv(DATA_FILE)
    for column in ("ingredients", "tags", "steps", "nutrition"):
        if column in df:
            df[column] = df[column].apply(parse_list)
    df["ingredients"] = df["ingredients"].apply(normalize_ingredient_list)
    df["minutes"] = pd.to_numeric(df["minutes"], errors="coerce")
    df["calories_per_serving"] = pd.to_numeric(df["calories_per_serving"], errors="coerce")
    return df


def read_csv_or_empty(path, columns):
    return pd.read_csv(path) if path.exists() else pd.DataFrame(columns=columns)


def ingredient_estimate(ingredients, catalog):
    """Calculate cost and calories independently when quantities and rates exist."""
    if catalog.empty:
        return None, None, "Add data/ingredient_catalog.csv with price_per_100g and kcal_per_100g."
    lookup = {normalize_ingredient(r.ingredient_name): r for r in catalog.itertuples()}
    cost_total = calories_total = 0.0
    cost_complete = calories_complete = True
    issues = []
    for item in ingredients:
        if not isinstance(item, dict) or not item.get("name") or item.get("quantity_g") is None:
            cost_complete = calories_complete = False
            issues.append("Ingredient quantities are missing; names alone cannot produce reliable totals.")
            continue
        row = lookup.get(normalize_ingredient(item["name"]))
        if row is None:
            cost_complete = calories_complete = False
            issues.append(f"Catalog data is missing for {item['name']}.")
            continue
        factor = float(item["quantity_g"]) / 100
        price = getattr(row, "price_per_100g", None)
        kcal = getattr(row, "kcal_per_100g", None)
        if price is None or pd.isna(price):
            cost_complete = False
            issues.append(f"Price is missing for {item['name']}.")
        else:
            cost_total += float(price) * factor
        if kcal is None or pd.isna(kcal):
            calories_complete = False
            issues.append(f"Nutrition data is missing for {item['name']}.")
        else:
            calories_total += float(kcal) * factor
    cost = round(cost_total, 2) if cost_complete else None
    calories = round(calories_total) if calories_complete else None
    return cost, calories, "; ".join(dict.fromkeys(issues)) or None


st.set_page_config(page_title="Smart Cart Recipe Recommender", page_icon="🍲", layout="wide")
st.title("🍲 Smart Cart: Inventory-Aware Recipe Recommendations")
st.caption("Seller inventory and supply conditions drive combination offers; recipes make those offers useful to customers.")

if not DATA_FILE.exists():
    st.error("Recipe data not found. Place RAW_recipes.csv beside preprocess.py and run python preprocess.py.")
    st.stop()

recipes = load_recipes()
classified = read_csv_or_empty(CLASSIFICATION_FILE, ["ingredient_name", "recipe_frequency", "frequency_ratio", "ingredient_frequency_category"])
catalog = read_csv_or_empty(CATALOG_FILE, ["ingredient_name", "price_per_100g", "kcal_per_100g"])
pantry_df = read_csv_or_empty(PANTRY_FILE, ["ingredient_name", "enabled", "notes"])
pantry_candidates = read_csv_or_empty(PANTRY_CANDIDATES_FILE, ["ingredient_name", "recipe_frequency", "frequency_ratio"])
# Core pantry staples are explicitly curated; the CSV adds household-specific approvals.
DEFAULT_PANTRY = {
    "salt", "sugar", "water", "vegetable oil", "black pepper",
    "turmeric", "cumin", "coriander powder", "chilli powder",
}
if not pantry_df.empty:
    enabled_values = pantry_df["enabled"].astype(str).str.casefold().isin(["true", "1", "yes", "y"])
    pantry_items = DEFAULT_PANTRY | set(pantry_df.loc[enabled_values, "ingredient_name"].map(normalize_ingredient))
else:
    pantry_items = DEFAULT_PANTRY
tabs = st.tabs(["Customer recommendations", "Seller inventory & combo offers", "Create your recipe", "Ingredient price catalog"])

with tabs[0]:
    st.header("1. Meal preference and context")
    sort_preference = st.radio("Sort recipes by", ["Calories", "Time Taken", "Budget Friendly"], horizontal=True)
    now = datetime.now().astimezone()
    hour = now.hour
    meal_period = "Breakfast" if 5 <= hour < 11 else "Lunch" if 11 <= hour < 16 else "Dinner" if 17 <= hour < 22 else "Light meal"
    st.info(f"Local system time: {now.strftime('%I:%M %p')} · Suggested meal period: **{meal_period}**")
    schedule = st.selectbox("Optional schedule context", ["No schedule preference", "Busy / short break", "After workout", "Late study/work", "Family meal"])
    context = {"Busy / short break": "quick meals", "After workout": "protein-conscious meals", "Late study/work": "light and convenient meals", "Family meal": "shareable meals"}.get(schedule, meal_period.lower() + " options")
    st.caption(f"Contextual suggestion: {context}. Time and schedule do not determine a person's actual mood.")

    st.header("2. Select cart ingredients")
    all_ingredients = list({item for values in recipes["ingredients"] for item in values})
    frequency_lookup = classified.set_index("ingredient_name")["recipe_frequency"].to_dict() if not classified.empty else {}
    all_ingredients.sort(key=lambda item: (frequency_lookup.get(item, float("inf")), item.casefold()))
    # Approved pantry staples are hidden by default, but can be selected when needed.
    show_pantry = st.checkbox("Include household pantry staples in the ingredient list", value=False)
    selectable = [x for x in all_ingredients if show_pantry or x not in pantry_items]
    selected_before_filter = st.session_state.get("cart_ingredients", [])
    options = list(dict.fromkeys(selectable + selected_before_filter))
    price_lookup = {}
    if not catalog.empty and "ingredient_name" in catalog.columns and "price_per_100g" in catalog.columns:
        for row in catalog.itertuples():
            try:
                price_lookup[normalize_ingredient(row.ingredient_name)] = float(row.price_per_100g)
            except (TypeError, ValueError):
                pass
    selected = st.multiselect(
        "Search and select ingredients individually", options, key="cart_ingredients",
        format_func=lambda item: (
            f"{item.title()} — ₹{price_lookup[normalize_ingredient(item)]:.2f}/100g"
            if normalize_ingredient(item) in price_lookup else item.title()
        ),
    )
    st.write(f"Items in cart: **{len(selected)}**")
    if selected:
        st.caption("Enter the quantity you intend to buy/use. Prices are estimates based on the catalog rate per 100 g.")
        price_rows = []
        cart_total = 0.0
        priced_items = 0
        for item in selected:
            quantity_g = st.number_input(
                f"{item.title()} quantity (g)",
                min_value=1.0,
                value=100.0,
                step=50.0,
                key=f"cart_quantity_{normalize_ingredient(item)}",
            )
            rate = price_lookup.get(normalize_ingredient(item))
            line_total = round(rate * quantity_g / 100, 2) if rate is not None else None
            if line_total is not None:
                cart_total += line_total
                priced_items += 1
            price_rows.append({
                "Ingredient": item.title(),
                "Quantity (g)": quantity_g,
                "Price / 100 g (₹)": rate,
                "Estimated item total (₹)": line_total,
            })
        st.dataframe(pd.DataFrame(price_rows), hide_index=True, use_container_width=True)
        if priced_items == len(selected):
            st.metric("Estimated total for selected ingredients", f"₹{cart_total:.2f}")
        else:
            st.warning(f"Total is partial: catalog prices are missing for {len(selected) - priced_items} selected ingredient(s).")

    with st.expander("Review frequency-based pantry candidates"):
        st.caption("These ingredients occur frequently in the recipe dataset. Frequency makes them candidates only; approve them only if they are normally stocked in your target households.")
        if pantry_candidates.empty:
            st.info("No candidate file yet. Run python preprocess.py to generate it.")
        else:
            approved = pantry_items
            pending = pantry_candidates[~pantry_candidates["ingredient_name"].map(normalize_ingredient).isin(approved)]
            st.dataframe(pending.head(50), hide_index=True, use_container_width=True)
            to_approve = st.multiselect("Select candidates to add to the pantry list", pending["ingredient_name"].tolist())
            if st.button("Approve selected pantry candidates", disabled=not to_approve):
                additions = pd.DataFrame([{"ingredient_name": name, "enabled": True, "notes": "Approved from recipe-frequency candidates"} for name in to_approve])
                defaults = pd.DataFrame([{"ingredient_name": item, "enabled": True, "notes": "Core manually curated household pantry staple"} for item in sorted(DEFAULT_PANTRY)])
                combined = pd.concat([defaults, pantry_df, additions], ignore_index=True).drop_duplicates(subset=["ingredient_name"], keep="last")
                combined.to_csv(PANTRY_FILE, index=False)
                st.success("Pantry list updated. Rerun the app to apply the changes.")

    st.header("3. Recipes using your cart items")
    if len(selected) < 3:
        st.info(f"Select {3-len(selected)} more item(s) to display recommendations.")
    else:
        matches = find_ranked_matches(recipes, selected, pantry_items=pantry_items)
        if matches.empty:
            st.warning("No recipes contain any of the selected ingredients.")
        else:
            max_matches = int(matches["_match_count"].max())
            st.caption(f"Your recommendations match up to {max_matches} of your {len(selected)} selected cart items.")
            matches, budget_cost_available = sort_recipes(matches, sort_preference)
            if sort_preference == "Budget Friendly" and not budget_cost_available:
                st.warning(
                    "Budget Friendly sorting is currently unavailable for these recipes. "
                    "The source dataset does not provide ingredient quantities, and no "
                    "reliable recipe-level cost estimates are available. For now, recipes "
                    "are ordered by fewer additional ingredients, then shorter cooking time. "
                    "Add recipe ingredient quantities and catalog prices to enable cost sorting."
                )
            elif (
                sort_preference == "Budget Friendly"
                and "estimated_cost" in matches.columns
                and matches["estimated_cost"].isna().any()
            ):
                missing_costs = int(matches["estimated_cost"].isna().sum())
                st.warning(
                    f"{missing_costs} recipe(s) have no reliable cost estimate and are "
                    "placed after recipes with known costs. Their actual affordability "
                    "cannot be compared until ingredient quantities and prices are available."
                )
            for _, recipe in matches.iterrows():
                with st.container(border=True):
                    st.subheader(str(recipe["name"]))
                    used = recipe["_matched_ingredients"]
                    st.write(f"**Uses {len(used)} of your {len(selected)} cart items:** " + ", ".join(used))
                    if len(selected) > 3 and len(used) >= 3:
                        st.success("This recipe uses at least 3 items from your selected cart.")
                    required = int(recipe["_required_count"])
                    if required == 0:
                        st.success("✓ ZERO ADDITIONAL INGREDIENTS REQUIRED — everything needed is already in your cart.")
                    else:
                        st.write(f"Additional ingredients required: **{required}**")
                    a, b = st.columns(2)
                    a.metric("Cooking time", f"{int(recipe['minutes'])} min" if pd.notna(recipe["minutes"]) else "Unavailable")
                    b.metric("Dataset calories / serving", f"{round(recipe['calories_per_serving'])} kcal" if pd.notna(recipe["calories_per_serving"]) else "Unavailable")
                    st.caption("Existing dataset recipes do not provide reliable per-ingredient quantities, so an exact total recipe cost cannot be calculated from ingredient names alone. Catalog prices are shown above when available.")
                    with st.expander("Cooking instructions"):
                        for i, step in enumerate(recipe.get("steps", []), 1):
                            st.write(f"{i}. {step}")

with tabs[1]:
    st.header("Seller inventory drives combination discounts")
    st.write("Offers are generated from surplus stock while protecting the seller's minimum margin.")
    st.caption("Upload a CSV with: ingredient_name, stock_qty, required_qty, unit_cost, unit_price.")
    upload = st.file_uploader("Upload current inventory", type=["csv"])
    inventory = pd.read_csv(upload) if upload is not None else read_csv_or_empty(INVENTORY_FILE, ["ingredient_name", "stock_qty", "required_qty", "unit_cost", "unit_price"])
    if inventory.empty:
        st.warning("No inventory loaded. Add data/seller_inventory.csv or upload an inventory CSV.")
    else:
        st.dataframe(inventory, use_container_width=True)
        max_discount = st.slider("Maximum discount (%)", 0, 40, 15)
        minimum_margin = st.slider("Minimum seller margin after discount (%)", 0, 30, 5)
        min_items = st.selectbox("Minimum items per combo", [2, 3], index=0)
        max_items = st.selectbox("Maximum items per combo", [2, 3, 4], index=2)
        offers = generate_combo_offers(inventory, max_discount=max_discount, min_items=min_items, max_items=max_items, minimum_margin_pct=minimum_margin)
        if not offers:
            st.info("No eligible combinations. Items need surplus stock and positive margin after discount.")
        for offer in offers[:25]:
            st.success(f"{' + '.join(offer['items'])} — {offer['discount_pct']}% off")
            st.caption(offer["reason"])

with tabs[2]:
    st.header("Create and save your own recipe")
    with st.form("custom_recipe"):
        name = st.text_input("Recipe name")
        servings = st.number_input("Servings", min_value=1, value=2)
        minutes = st.number_input("Cooking time (minutes)", min_value=1, value=30)
        st.write("Enter each ingredient with its quantity in grams for cost/calorie calculation.")
        ingredient_rows = st.text_area("Ingredients (one per line: ingredient name, quantity in grams)", placeholder="tomato, 150\nonion, 100\nrice, 200")
        instructions = st.text_area("Cooking instructions (one step per line)")
        save = st.form_submit_button("Save recipe")
    if save:
        if not name.strip() or not ingredient_rows.strip():
            st.error("Recipe name and at least one ingredient are required.")
        else:
            parsed = []
            invalid = []
            for line in ingredient_rows.splitlines():
                parts = [x.strip() for x in line.split(",", 1)]
                try:
                    if len(parts) != 2 or not parts[0] or float(parts[1]) <= 0:
                        raise ValueError
                    parsed.append({"name": parts[0], "quantity_g": float(parts[1])})
                except ValueError:
                    invalid.append(line)
            if invalid:
                st.error("Could not parse these lines; use 'ingredient, quantity in grams': " + "; ".join(invalid))
            else:
                cost, kcal, issue = ingredient_estimate(parsed, catalog)
                import json
                record = {"name": name.strip(), "servings": int(servings), "minutes": int(minutes), "ingredients": json.dumps(parsed), "steps": json.dumps([x.strip() for x in instructions.splitlines() if x.strip()]), "estimated_cost": cost, "estimated_calories": kcal}
                pd.DataFrame([record]).to_csv(CUSTOM_FILE, mode="a", header=not CUSTOM_FILE.exists(), index=False)
                st.success("Recipe saved.")
                if cost is not None:
                    st.info(f"Estimated total ingredient cost: ₹{cost:.2f} (whole recipe)")
                if kcal is not None:
                    st.info(f"Estimated total calories: {kcal} kcal (whole recipe)")
                if issue:
                    st.warning(issue)


with tabs[3]:
    st.header("Ingredient-wise price catalog")
    st.write("Enter the market price for each ingredient using a consistent base quantity of 100 grams.")
    st.caption("Example: if 1 kg of rice costs ₹60, enter ₹6 as the price per 100 g. Leave unknown prices blank; the app will not guess them.")
    if catalog.empty:
        st.warning("No ingredient rows found. Run python preprocess.py after adding RAW_recipes.csv.")
    else:
        edited_catalog = st.data_editor(
            catalog,
            num_rows="dynamic",
            use_container_width=True,
            key="ingredient_price_catalog_editor",
            column_config={
                "ingredient_name": st.column_config.TextColumn("Ingredient", required=True),
                "price_per_100g": st.column_config.NumberColumn("Price per 100 g (₹)", min_value=0.0, format="%.2f"),
                "kcal_per_100g": st.column_config.NumberColumn("Calories per 100 g", min_value=0.0, format="%.1f"),
            },
        )
        if st.button("Save ingredient prices"):
            save_catalog = edited_catalog.copy()
            save_catalog["ingredient_name"] = save_catalog["ingredient_name"].fillna("").astype(str).str.strip()
            save_catalog = save_catalog[save_catalog["ingredient_name"] != ""]
            save_catalog["_normalized_name"] = save_catalog["ingredient_name"].map(normalize_ingredient)
            if save_catalog["_normalized_name"].duplicated().any():
                st.error("Duplicate ingredient names found after normalization. Keep only one row per ingredient.")
            else:
                save_catalog = save_catalog.drop(columns=["_normalized_name"])
                for column in ("price_per_100g", "kcal_per_100g"):
                    save_catalog[column] = pd.to_numeric(save_catalog[column], errors="coerce")
                    if (save_catalog[column].dropna() < 0).any():
                        st.error(f"{column} cannot contain negative values.")
                        st.stop()
                save_catalog.to_csv(CATALOG_FILE, index=False)
                st.success("Ingredient price catalog saved.")
                st.cache_data.clear()
                st.rerun()
