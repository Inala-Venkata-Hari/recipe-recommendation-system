import ast
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from ingredient_normalization import normalize_ingredient, normalize_ingredient_list
from recipe_matching import find_ranked_matches
from inventory_discounts import generate_combo_offers

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "recipes_cleaned.csv"
CLASSIFICATION_FILE = ROOT / "data" / "ingredients_classified.csv"
INVENTORY_FILE = ROOT / "data" / "seller_inventory.csv"
CATALOG_FILE = ROOT / "data" / "ingredient_catalog.csv"
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
    """Calculate totals only when each ingredient has a known quantity and catalog rate."""
    if catalog.empty:
        return None, None, "Add data/ingredient_catalog.csv with price_per_100g and kcal_per_100g."
    lookup = {normalize_ingredient(r.ingredient_name): r for r in catalog.itertuples()}
    cost = calories = 0.0
    for item in ingredients:
        if not isinstance(item, dict) or not item.get("name") or item.get("quantity_g") is None:
            return None, None, "Ingredient quantities are missing; names alone cannot produce reliable totals."
        row = lookup.get(normalize_ingredient(item["name"]))
        if row is None or pd.isna(row.price_per_100g) or pd.isna(row.kcal_per_100g):
            return None, None, f"Price/nutrition data is missing for {item['name']}."
        factor = float(item["quantity_g"]) / 100
        cost += float(row.price_per_100g) * factor
        calories += float(row.kcal_per_100g) * factor
    return round(cost, 2), round(calories), None


st.set_page_config(page_title="Smart Cart Recipe Recommender", page_icon="🍲", layout="wide")
st.title("🍲 Smart Cart: Inventory-Aware Recipe Recommendations")
st.caption("Seller inventory and supply conditions drive combination offers; recipes make those offers useful to customers.")

if not DATA_FILE.exists():
    st.error("Recipe data not found. Place RAW_recipes.csv beside preprocess.py and run python preprocess.py.")
    st.stop()

recipes = load_recipes()
classified = read_csv_or_empty(CLASSIFICATION_FILE, ["ingredient_name", "recipe_frequency", "frequency_ratio", "ingredient_frequency_category"])
catalog = read_csv_or_empty(CATALOG_FILE, ["ingredient_name", "price_per_100g", "kcal_per_100g"])
tabs = st.tabs(["Customer recommendations", "Seller inventory & combo offers", "Create your recipe"])

with tabs[0]:
    st.header("1. Meal preference and context")
    preference = st.radio("Choose a preference", ["Balanced meal", "Low calorie", "Quick meal", "Budget-friendly"], horizontal=True)
    now = datetime.now().astimezone()
    hour = now.hour
    meal_period = "Breakfast" if 5 <= hour < 11 else "Lunch" if 11 <= hour < 16 else "Dinner" if 17 <= hour < 22 else "Light meal"
    st.info(f"Local system time: {now.strftime('%I:%M %p')} · Suggested meal period: **{meal_period}**")
    schedule = st.selectbox("Optional schedule context", ["No schedule preference", "Busy / short break", "After workout", "Late study/work", "Family meal"])
    context = {"Busy / short break": "quick meals", "After workout": "protein-conscious meals", "Late study/work": "light and convenient meals", "Family meal": "shareable meals"}.get(schedule, meal_period.lower() + " options")
    st.caption(f"Contextual suggestion: {context}. Time and schedule do not determine a person's actual mood.")

    st.header("2. Select cart ingredients")
    all_ingredients = sorted({item for values in recipes["ingredients"] for item in values}, key=str.casefold)
    if not classified.empty:
        category_order = {"Common": 0, "Moderately common": 1, "Specialized": 2, "Rare / recipe-specific": 3}
        freq = classified.set_index("ingredient_name").to_dict("index")
        category_filter = st.selectbox("Filter ingredient category", ["All categories", "Common", "Moderately common", "Specialized", "Rare / recipe-specific"])
        sort_choice = st.selectbox("Ingredient ordering", ["Most frequently used first", "Specialized / unique first", "Alphabetical"])
        if sort_choice == "Most frequently used first":
            all_ingredients.sort(key=lambda x: (category_order.get(freq.get(x, {}).get("ingredient_frequency_category"), 4), -freq.get(x, {}).get("recipe_frequency", 0), x.casefold()))
        elif sort_choice == "Specialized / unique first":
            all_ingredients.sort(key=lambda x: (-category_order.get(freq.get(x, {}).get("ingredient_frequency_category"), -1), freq.get(x, {}).get("recipe_frequency", 0), x.casefold()))
        if category_filter != "All categories":
            visible = [x for x in all_ingredients if freq.get(x, {}).get("ingredient_frequency_category") == category_filter]
        else:
            visible = all_ingredients
    else:
        visible = all_ingredients
    # Keep already-selected items available if the filter changes, so a category
    # switch never silently discards a cart selection.
    selected_before_filter = st.session_state.get("cart_ingredients", [])
    options = list(dict.fromkeys(visible + selected_before_filter))
    selected = st.multiselect("Search and select items individually (bulk add has been removed)", options, key="cart_ingredients")
    st.write(f"Items in cart: **{len(selected)}**")

    st.header("3. Recipes using your cart items")
    if len(selected) < 3:
        st.info(f"Select {3-len(selected)} more item(s) to display recommendations.")
    else:
        matches = find_ranked_matches(recipes, selected)
        if matches.empty:
            st.warning("No recipes contain any of the selected ingredients.")
        else:
            max_matches = int(matches["_match_count"].max())
            st.caption(f"Top matches use {max_matches} of your {len(selected)} selected items.")
            if preference == "Low calorie":
                matches = matches[matches["calories_per_serving"].notna() & (matches["calories_per_serving"] <= 500)]
            elif preference == "Quick meal":
                matches = matches[matches["minutes"].notna() & (matches["minutes"] <= 30)]
            elif preference == "Balanced meal":
                matches = matches[matches["calories_per_serving"].notna() & (matches["calories_per_serving"] <= 600) & matches["minutes"].notna() & (matches["minutes"] <= 45)]
            if matches.empty:
                st.warning("No matching recipes satisfy this preference.")
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
                    st.caption("Exact ingredient-based cost/calories require ingredient quantities and a populated ingredient catalog; recipe names alone are insufficient.")
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
                if issue:
                    st.warning(issue)
                else:
                    st.info(f"Estimated ingredient cost: {cost:.2f} · Estimated calories: {kcal} kcal (whole recipe)")
