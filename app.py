import ast
from inventory_batches import create_batch
from catalog_import import merge_catalog
from checkout import offer_key, checkout_lines, validate_bundles, best_missing_combos
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from ingredient_normalization import normalize_ingredient, normalize_ingredient_list
from recipe_matching import find_ranked_matches
from recipe_sorting import sort_recipes
from inventory_discounts import generate_combo_offers, score_inventory

ROOT = Path(__file__).parent
# An explicit RECIPE_DATA_DIR always wins. Otherwise, use the bundled synthetic
# demo dataset when present so its recipe quantities and ingredient prices load
# together; fall back to the regular data directory for normal deployments.
configured_data_dir = os.environ.get("RECIPE_DATA_DIR")
SYNTHETIC_DATA_DIR = ROOT / "data" / "synthetic_demo"
DATA_DIR = (
    Path(configured_data_dir)
    if configured_data_dir
    else SYNTHETIC_DATA_DIR if (SYNTHETIC_DATA_DIR / "recipes_cleaned.csv").exists()
    else ROOT / "data"
)
DATA_FILE = DATA_DIR / "recipes_cleaned.csv"
CLASSIFICATION_FILE = DATA_DIR / "ingredients_classified.csv"
INVENTORY_FILE = DATA_DIR / "seller_inventory.csv"
CATALOG_FILE = DATA_DIR / "ingredient_catalog.csv"
PANTRY_FILE = DATA_DIR / "pantry_ingredients.csv"
PANTRY_CANDIDATES_FILE = DATA_DIR / "pantry_candidates.csv"
CUSTOM_FILE = DATA_DIR / "custom_recipes.csv"


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
    for column in ("ingredients", "ingredient_quantities", "tags", "steps", "nutrition"):
        if column in df:
            df[column] = df[column].apply(parse_list)
    df["ingredients"] = df["ingredients"].apply(normalize_ingredient_list)
    df["minutes"] = pd.to_numeric(df["minutes"], errors="coerce")
    df["calories_per_serving"] = pd.to_numeric(df["calories_per_serving"], errors="coerce")
    return df


def read_csv_or_empty(path, columns):
    return pd.read_csv(path) if path.exists() and path.stat().st_size > 0 else pd.DataFrame(columns=columns)


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


from recipe_costs import add_recipe_cost_estimates


def add_missing_items(items, recipe_quantities, current_offers, current_inventory):
    cart = list(st.session_state.get("cart_ingredients", []))
    quantities = {
        normalize_ingredient(entry["name"]): float(entry["quantity_g"])
        for entry in recipe_quantities
        if isinstance(entry, dict) and entry.get("name") and entry.get("quantity_g") is not None
    }
    for item in items:
        if item not in cart:
            cart.append(item)
            amount = quantities.get(normalize_ingredient(item), 100.0)
            st.session_state[f"cart_quantity_{normalize_ingredient(item)}"] = max(1.0, amount)
    st.session_state["cart_ingredients"] = cart
    automatic = best_missing_combos(items, current_offers, current_inventory,
                                    st.session_state.get("chosen_combos", []))
    for offer in automatic:
        add_combo(offer)
    st.session_state.pop("demo_receipt", None)


def add_combo(offer):
    chosen = st.session_state.get("chosen_combos", [])
    occupied = {name for existing in chosen for name in existing["items"]}
    if occupied.intersection(offer["items"]):
        st.session_state["combo_message"] = "Remove the overlapping combo before choosing this one."
        return
    cart = list(st.session_state.get("cart_ingredients", []))
    for name in offer["items"]:
        if name not in cart:
            cart.append(name)
        key = f"cart_quantity_{normalize_ingredient(name)}"
        st.session_state[key] = max(100.0, float(st.session_state.get(key, 0)))
    st.session_state["cart_ingredients"] = cart
    st.session_state["chosen_combos"] = chosen + [offer]
    st.session_state.pop("demo_receipt", None)


def remove_combo(index):
    st.session_state["chosen_combos"].pop(index)
    st.session_state.pop("demo_receipt", None)


def reset_demo():
    st.session_state.clear()


st.set_page_config(page_title="Smart Cart Recipe Recommender", page_icon="🍲", layout="wide")
st.title("🍲 Smart Cart: Inventory-Aware Recipe Recommendations")
st.button("Reset demo", on_click=reset_demo, help="Reset this session’s cart, combos, receipt, upload and controls. Saved CSV files are unchanged.")
st.caption("Seller inventory and supply conditions drive combination offers; recipes make those offers useful to customers.")
if DATA_DIR == SYNTHETIC_DATA_DIR:
    st.info("Presentation demo • Synthetic inventory, prices and nutrition; no measured sales uplift. Snapshot date: 2026-11-05.")

if not DATA_FILE.exists():
    st.error(f"Recipe data not found in {DATA_DIR}. Run python generate_synthetic_data.py or python preprocess.py.")
    st.stop()

recipes = load_recipes()
classified = read_csv_or_empty(CLASSIFICATION_FILE, ["ingredient_name", "recipe_frequency", "frequency_ratio", "ingredient_frequency_category"])
catalog = read_csv_or_empty(CATALOG_FILE, ["ingredient_name", "price_per_100g", "kcal_per_100g"])
recipes = add_recipe_cost_estimates(recipes, catalog)
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

offers = []
with tabs[1]:
    st.header("Seller inventory drives combination discounts")
    st.write("Discounts increase with stock age, expiry risk and expected excess, while preserving the seller's minimum margin.")
    st.caption("Upload a CSV with: ingredient_name, stock_qty, required_qty, unit_cost, unit_price.")
    st.caption("Optional batch columns: batch_id, received_date, expiry_date, avg_daily_sales, target_holding_days, markdown_window_days. Quantities and prices must use the same stock unit. Missing signals use surplus stock as a fallback.")
    st.caption("Recipe-frequency policy: Common ×1.0, Moderately common ×1.1, Specialized ×1.2, Rare ×1.3. The multiplier boosts existing inventory urgency; it does not measure sales demand. Unknown ingredients use ×1.0.")
    with st.expander("Classification-based discount parameters"):
        from inventory_discounts import classification_parameters
        st.dataframe(pd.DataFrame([
            {"ingredient_name": name, "frequency_ratio": values[0], "category": values[1], "discount_multiplier": values[2]}
            for name, values in classification_parameters(classified).items()
        ]), width="stretch")
    assessment_date = st.date_input("Inventory assessment date", value=datetime(2026, 11, 5).date() if DATA_DIR == SYNTHETIC_DATA_DIR else datetime.now().date())
    upload = st.file_uploader("Upload current inventory", type=["csv"])
    try:
        inventory = pd.read_csv(upload) if upload is not None else read_csv_or_empty(INVENTORY_FILE, ["ingredient_name", "stock_qty", "required_qty", "unit_cost", "unit_price"])
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError, ValueError):
        st.error("Could not read inventory. Upload a UTF-8 CSV with a header row and consistent columns.")
        inventory = pd.DataFrame()
    st.download_button("Download inventory CSV template", (ROOT / "data" / "seller_inventory_template.csv").read_bytes(),
                       file_name="seller_inventory_template.csv", mime="text/csv")
    if st.session_state.get("batch_notice"):
        st.success(st.session_state.pop("batch_notice"))
    with st.expander("Create inventory batch from ingredient catalog"):
        st.caption("New batches use the catalog selling price per 100 g. Stock, daily sales and costs are per 100 g pack. Existing batches retain their saved prices; changing the catalog does not silently reprice them.")
        if upload is not None:
            st.info("Clear the inventory upload to create a batch in the saved inventory.")
        elif catalog.empty:
            st.info("Upload or fill the ingredient price catalog first.")
        else:
            batch_ingredient = st.selectbox("Batch ingredient", sorted(catalog.ingredient_name.dropna().unique()), key="batch_ingredient")
            catalog_row = catalog[catalog.ingredient_name == batch_ingredient].iloc[0]
            batch_price = pd.to_numeric(catalog_row.price_per_100g, errors="coerce")
            st.write(f"Catalog selling price: ₹{batch_price:.2f} / 100 g pack" if pd.notna(batch_price) else "Catalog price is missing.")
            frequency = classification_parameters(classified).get(normalize_ingredient(batch_ingredient))
            if frequency:
                st.caption(f"Recipe frequency: {frequency[0]:.1%} · {frequency[1]} · discount urgency multiplier ×{frequency[2]:.1f}")
            else:
                st.caption("Unclassified ingredient: neutral discount multiplier ×1.0.")
            with st.form("create_inventory_batch"):
                batch_id = st.text_input("New batch ID")
                batch_stock = st.number_input("Stock (100 g packs)", min_value=1, value=50)
                batch_required = st.number_input("Required supply (100 g packs)", min_value=0, value=10)
                batch_cost = st.number_input("Acquisition cost per 100 g pack (₹)", min_value=0.0, value=1.0, step=0.1)
                batch_received = st.date_input("Batch received date", value=assessment_date)
                batch_expiry = st.date_input("Batch expiry date", value=assessment_date + timedelta(days=7))
                batch_sales = st.number_input("Average daily sales (100 g packs)", min_value=0.0, value=2.0)
                batch_holding = st.number_input("Target holding days", min_value=1, value=7)
                batch_window = st.number_input("Markdown window days", min_value=1, value=7)
                if st.form_submit_button("Create batch and calculate discounts"):
                    try:
                        record = create_batch(catalog, inventory, batch_ingredient, batch_id, batch_stock,
                                              batch_required, batch_cost, batch_received, batch_expiry,
                                              batch_sales, batch_holding, batch_window, assessment_date)
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        INVENTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
                        pd.concat([inventory, pd.DataFrame([record])], ignore_index=True).to_csv(INVENTORY_FILE, index=False)
                        st.session_state["batch_notice"] = "Batch created from catalog price. Frequency-based discounts have been recalculated."
                        st.session_state.pop("demo_receipt", None)
                        st.rerun()
    if inventory.empty:
        st.warning("No inventory loaded. Create a batch from the catalog or upload an inventory CSV.")
    else:
        scored = score_inventory(inventory, today=assessment_date, classified=classified)
        st.subheader("Inventory decisions")
        st.dataframe(scored, width="stretch")
        if not scored.empty:
            excluded = scored[~scored["eligible"]]
            st.metric("Excluded batches", len(excluded))
            if not excluded.empty:
                st.dataframe(excluded[[c for c in ["ingredient_name", "batch_id", "exclusion_reason"] if c in excluded]], width="stretch")
        if scored.empty:
            st.warning("Inventory requires ingredient_name, stock_qty, required_qty, unit_cost and unit_price.")
        elif (~scored["eligible"]).any():
            st.warning("Some rows are excluded; inspect exclusion_reason above. Expiry dates are treated as exclusive.")
        max_discount = st.slider("Maximum discount (%)", 0, 40, 15)
        minimum_margin = st.slider("Minimum seller margin after discount (%)", 0, 30, 5)
        min_items = st.selectbox("Minimum items per combo", [2, 3], index=0)
        max_items = st.selectbox("Maximum items per combo", [2, 3, 4], index=2)
        if min_items > max_items:
            st.warning("Maximum items per combo must be at least the minimum. Adjust the combo size controls.")
        else:
            offers = generate_combo_offers(inventory, max_discount=max_discount, min_items=min_items, max_items=max_items, minimum_margin_pct=minimum_margin, today=assessment_date, classified=classified)
        if not offers:
            st.info("No eligible combinations. Items need markdown urgency and sufficient margin after discount.")
        if offers:
            st.subheader("Seller decision dashboard")
            st.caption("Each row is an alternative offer. Offers can share stock; totals are not additive. Prices are in INR; stock units are specified per ingredient.")
            left, middle, right = st.columns(3)
            left.metric("Available offers", len(offers))
            middle.metric("Largest discount", f"{max(o['discount_pct'] for o in offers):.1f}%")
            right.metric("Lowest offer margin", f"{min(o['margin_pct'] for o in offers):.1f}%")
            decisions = pd.DataFrame([{
                "Combo": " + ".join(o["items"]), "Quantities": o["quantity_description"],
                "Batches": ", ".join(o["batch_ids"]), "Discount (%)": o["discount_pct"],
                "Original price (INR)": o["original_price"], "Offer price (INR)": o["offer_price"],
                "Cost (INR)": o["cost"], "Profit (INR)": o["profit"],
                "Margin (%)": round(o["margin_pct"], 2), "Savings (INR)": o["savings"],
                "Margin cap applied": o["margin_limited"], "Reason breakdown": o["breakdown"]
            } for o in offers])
            st.dataframe(decisions, width="stretch", hide_index=True)
            st.download_button("Download proposed offers (CSV)", decisions.to_csv(index=False).encode("utf-8"),
                               file_name=f"proposed_offers_{assessment_date}.csv", mime="text/csv")
            for offer in offers[:10]:
                with st.expander(f"{' + '.join(offer['items'])} — {offer['discount_pct']}% off"):
                    st.write(offer["quantity_description"])
                    st.caption(offer["reason"])
                    st.write(offer["breakdown"])
                    useful = recipes[recipes["ingredients"].apply(lambda items: set(offer["items"]).issubset(set(items)))]
                    if not useful.empty:
                        st.write("Use together in: " + ", ".join(useful["name"].astype(str).head(3)))


with tabs[0]:
    st.header("1. Meal preference and context")
    sort_preference = st.radio("Break ties after fewest additional items by", ["Calories", "Time Taken", "Budget Friendly"], horizontal=True)
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
        cart_item_costs = {}
        cart_total = 0.0
        priced_items = 0
        for item in selected:
            st.session_state.setdefault(f"cart_quantity_{normalize_ingredient(item)}", 100.0)
            quantity_g = st.number_input(
                f"{item.title()} quantity (g)",
                min_value=1.0,
                step=50.0,
                key=f"cart_quantity_{normalize_ingredient(item)}",
            )
            rate = price_lookup.get(normalize_ingredient(item))
            line_total = round(rate * quantity_g / 100, 2) if rate is not None else None
            cart_item_costs[normalize_ingredient(item)] = line_total
            if line_total is not None:
                cart_total += line_total
                priced_items += 1
            price_rows.append({
                "Ingredient": item.title(),
                "Quantity (g)": quantity_g,
                "Price / 100 g (₹)": rate,
                "Estimated item total (₹)": line_total,
            })
        st.dataframe(pd.DataFrame(price_rows), hide_index=True, width="stretch")
        if priced_items == len(selected):
            st.metric("Regular catalog estimate", f"₹{cart_total:.2f}")
            try:
                effective_lines = checkout_lines(
                    {normalize_ingredient(n): float(st.session_state.get(f"cart_quantity_{normalize_ingredient(n)}", 100)) for n in selected},
                    price_lookup, st.session_state.get("chosen_combos", []), offers, inventory)
            except ValueError as exc:
                st.warning("Discounted total unavailable: " + str(exc))
            else:
                effective_total = sum(line["Payable (INR)"] for line in effective_lines)
                applied_savings = sum(line["Savings (INR)"] for line in effective_lines)
                left, right = st.columns(2)
                left.metric("Effective cart price", f"₹{effective_total:.2f}")
                right.metric("Applied combo savings", f"₹{applied_savings:.2f}")
        else:
            st.warning(f"Total is partial: catalog prices are missing for {len(selected) - priced_items} selected ingredient(s).")

    with st.expander("Review frequency-based pantry candidates"):
        st.caption("These ingredients occur frequently in the recipe dataset. Frequency makes them candidates only; approve them only if they are normally stocked in your target households.")
        if pantry_candidates.empty:
            st.info("No candidate file yet. Run python preprocess.py to generate it.")
        else:
            approved = pantry_items
            pending = pantry_candidates[~pantry_candidates["ingredient_name"].map(normalize_ingredient).isin(approved)]
            st.dataframe(pending.head(50), hide_index=True, width="stretch")
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
            st.caption("Recipes are always sorted by additional ingredients required: 0, 1, 2, … . Your selected preference breaks ties only.")
            matches, budget_cost_available = sort_recipes(matches, sort_preference)
            if sort_preference == "Budget Friendly" and not budget_cost_available:
                st.warning(
                    "Budget Friendly sorting cannot calculate costs for these matches because "
                    "some recipes are missing ingredient quantities or catalog prices. "
                    "Those recipes are ordered after recipes with known costs within the same additional-item count."
                )
            elif (
                sort_preference == "Budget Friendly"
                and "estimated_cost" in matches.columns
                and matches["estimated_cost"].isna().any()
            ):
                missing_costs = int(matches["estimated_cost"].isna().sum())
                st.warning(
                    f"{missing_costs} recipe(s) have no reliable cost estimate and are "
                    "placed after recipes with known costs within the same additional-item count. Their actual affordability "
                    "cannot be compared until ingredient quantities and prices are available."
                )
            for _, recipe in matches.iterrows():
                with st.container(border=True):
                    st.subheader(str(recipe["name"]))
                    used = recipe["_matched_ingredients"]
                    used_labels = []
                    used_costs = []
                    for item in used:
                        item_cost = cart_item_costs.get(normalize_ingredient(item))
                        used_costs.append(item_cost)
                        used_labels.append(f"{item} (₹{item_cost:.2f})" if item_cost is not None else f"{item} (cost unavailable)")
                    total_label = (
                        f" — **Matched cart cost: ₹{sum(used_costs):.2f}**"
                        if all(cost is not None for cost in used_costs)
                        else " — **Matched cart cost unavailable**"
                    )
                    st.write(f"**Uses {len(used)} of your {len(selected)} cart items:** " + ", ".join(used_labels) + total_label)
                    st.caption("Matched cart cost uses your entered cart quantities; recipe cost below uses recipe quantities.")
                    required = int(recipe["_required_count"])
                    if required == 0:
                        st.success("✓ ZERO ADDITIONAL INGREDIENTS REQUIRED — everything needed is already in your cart or enabled pantry.")
                    else:
                        st.write(f"Additional ingredients required: **{required}**")
                    a, b = st.columns(2)
                    a.metric("Cooking time", f"{int(recipe['minutes'])} min" if pd.notna(recipe["minutes"]) else "Unavailable")
                    b.metric("Dataset calories / serving", f"{round(recipe['calories_per_serving'])} kcal" if pd.notna(recipe["calories_per_serving"]) else "Unavailable")
                    if pd.notna(recipe.get("estimated_cost")):
                        cost_col, serving_col = st.columns(2)
                        cost_col.metric("Estimated recipe cost", f"₹{recipe['estimated_cost']:.2f}")
                        serving_col.metric("Estimated cost / serving", f"₹{recipe['estimated_cost_per_serving']:.2f}")
                        st.caption("Estimate based on synthetic ingredient quantities and current catalog rates.")
                    else:
                        st.warning("Recipe cost unavailable: ingredient quantities or catalog prices are missing.")
                    additional_items = sorted(
                        set(normalize_ingredient_list(recipe["ingredients"]))
                        - set(normalize_ingredient_list(selected))
                        - set(pantry_items)
                    )
                    if additional_items:
                        st.write("**Additional items to get:** " + ", ".join(additional_items))
                        recipe_quantities = recipe.get("ingredient_quantities", [])
                        if not isinstance(recipe_quantities, list):
                            recipe_quantities = []
                        st.button("Add missing items to cart", key=f"add_missing_{recipe['id']}",
                                  on_click=add_missing_items, args=(additional_items, recipe_quantities, offers, inventory))
                        st.caption("Automatically applies the highest total savings from non-overlapping eligible combos for these missing items. Discounted items use at least one 100 g pack; other items use recipe quantities (or 100 g if unknown).")
                        relevant_offers = [
                            offer for offer in offers
                            if set(normalize_ingredient_list(offer["items"])).issubset(set(additional_items))
                        ]
                        if relevant_offers:
                            st.success("Discounted combinations are available for your additional items")
                            for offer in relevant_offers[:3]:
                                st.write(
                                    f"**{' + '.join(offer['items'])} — {offer['discount_pct']:.1f}% off** · "
                                    f"₹{offer['offer_price']:.2f} (regular ₹{offer['original_price']:.2f}) · "
                                    f"Save ₹{offer['savings']:.2f}"
                                )
                                st.caption("Bundle quantities: " + offer["quantity_description"])
                                bundle_rows = inventory[inventory["ingredient_name"].isin(offer["items"])]
                                checkout_supported = (
                                    "stock_unit" in bundle_rows and "batch_id" in bundle_rows
                                    and bundle_rows["stock_unit"].eq("100 g pack").all()
                                )
                                st.button("Add discounted combo to cart", key=f"add_combo_{recipe['id']}_{offer_key(offer)}",
                                          on_click=add_combo, args=(offer,), disabled=not checkout_supported)
                                if not checkout_supported:
                                    st.caption("Checkout needs defined 100 g packs and unique batch IDs for this inventory.")
                            st.caption("Alternative bundle offers; choose one. Bundle prices apply to the listed stock quantities and do not replace the whole-recipe cost estimate. Other additional items are priced separately.")
                        else:
                            st.caption("No discounted combination is available for these additional items under the current seller settings.")

    st.header("4. Simulated checkout")
    st.caption("Demo only: no payment is collected and no stock is reserved or deducted. Combo validation uses the seller assessment date and settings. Non-combo items use catalog price estimates.")
    if st.session_state.get("combo_message"):
        st.warning(st.session_state.pop("combo_message"))
    chosen = st.session_state.get("chosen_combos", [])
    for index, combo in enumerate(chosen):
        st.write("Selected combo: **" + " + ".join(combo["items"]) + f"** — ₹{combo['offer_price']:.2f}")
        st.button("Remove combo", key=f"remove_combo_{index}", on_click=remove_combo, args=(index,))
    if selected:
        quantities = {normalize_ingredient(name): float(st.session_state.get(f"cart_quantity_{normalize_ingredient(name)}", 100)) for name in selected}
        try:
            lines = checkout_lines(quantities, price_lookup, chosen, offers, inventory)
        except ValueError as exc:
            st.error(str(exc))
        else:
            checkout_df = pd.DataFrame(lines)
            st.dataframe(checkout_df, hide_index=True, width="stretch")
            available_ingredients = set(normalize_ingredient_list(selected)) | set(pantry_items)
            ready_recipes = recipes[recipes["ingredients"].apply(
                lambda items: bool(normalize_ingredient_list(items))
                and set(normalize_ingredient_list(items)).issubset(available_ingredients)
            )]
            if not ready_recipes.empty:
                st.success("With these items, you can make: " + ", ".join(ready_recipes["name"].astype(str)) + ".")
                st.caption("Based on ingredient availability, including enabled pantry staples; check recipe quantities before cooking.")
            regular = round(sum(line["Regular (INR)"] for line in lines), 2)
            payable = round(sum(line["Payable (INR)"] for line in lines), 2)
            a, b, c = st.columns(3)
            a.metric("Regular cart total", f"₹{regular:.2f}")
            b.metric("Combo savings", f"₹{regular-payable:.2f}")
            c.metric("Final demo total", f"₹{payable:.2f}")
            if st.button("Confirm simulated checkout"):
                # Revalidate immediately before generating the receipt.
                try:
                    confirmed = checkout_lines(quantities, price_lookup, chosen, offers, inventory)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    receipt = pd.DataFrame(confirmed)
                    receipt["Assessment date"] = str(assessment_date)
                    receipt["Status"] = "SIMULATED — no payment or stock deduction"
                    st.session_state["demo_receipt"] = receipt.to_csv(index=False).encode("utf-8")
            if st.session_state.get("demo_receipt"):
                st.success("Simulated receipt ready. This is a snapshot of the confirmed cart.")
                st.download_button("Download simulated receipt (CSV)", st.session_state["demo_receipt"],
                                   file_name="simulated_receipt.csv", mime="text/csv")
    else:
        st.info("Select cart ingredients or add a discounted combo to preview checkout.")

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
    st.download_button("Download price catalog CSV template",
                       "ingredient_name,price_per_100g,kcal_per_100g\n", file_name="ingredient_catalog_template.csv", mime="text/csv")
    catalog_upload = st.file_uploader("Upload ingredient price catalog (CSV)", type=["csv"], key="catalog_csv_upload")
    st.caption("Required: ingredient_name, price_per_100g. Optional: kcal_per_100g. Matching ingredients are updated; other ingredients are retained. Blank values clear the uploaded field; an omitted calorie column preserves existing calories.")
    if catalog_upload is not None:
        try:
            imported = pd.read_csv(catalog_upload)
            merged_catalog = merge_catalog(catalog, imported)
        except (ValueError, pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
            st.error("Catalog upload could not be applied: " + str(exc))
        else:
            st.write(f"Preview: {len(imported)} uploaded ingredient rows")
            st.dataframe(imported, hide_index=True, width="stretch")
            if st.button("Apply uploaded catalog"):
                CATALOG_FILE.parent.mkdir(parents=True, exist_ok=True)
                merged_catalog.to_csv(CATALOG_FILE, index=False)
                st.session_state.pop("ingredient_price_catalog_editor", None)
                st.session_state.pop("demo_receipt", None)
                st.session_state["catalog_upload_notice"] = "Uploaded ingredient prices saved. Cart and recipe estimates have been refreshed."
                st.cache_data.clear()
                st.rerun()
    if st.session_state.get("catalog_upload_notice"):
        st.success(st.session_state.pop("catalog_upload_notice"))
    if catalog.empty:
        st.info("Upload a CSV to create your ingredient catalog.")
    else:
        edited_catalog = st.data_editor(
            catalog,
            num_rows="dynamic",
            width="stretch",
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
