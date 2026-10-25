import ast
from pathlib import Path

import pandas as pd
import streamlit as st
from recipe_matching import find_ranked_matches

DATA_FILE = Path(__file__).parent / "data" / "recipes_cleaned.csv"


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
    df["minutes"] = pd.to_numeric(df["minutes"], errors="coerce")
    df["calories_per_serving"] = pd.to_numeric(df["calories_per_serving"], errors="coerce")
    return df


st.set_page_config(page_title="Smart Cart Recipe Recommender", page_icon="🍲", layout="wide")
st.title("🍲 Smart Cart Recipe Recommender")
st.caption("Choose a preference, then select the ingredients already in your cart. Results update automatically.")

if not DATA_FILE.exists():
    st.error("Recipe data not found. Place RAW_recipes.csv beside preprocess.py and run python preprocess.py.")
    st.stop()

recipes = load_recipes()
st.header("1. Choose your preference")
preference = st.radio(
    "What matters most for this meal?",
    ["Balanced meal", "Low calorie", "Quick meal", "Budget-friendly"],
    horizontal=True,
)

if preference == "Budget-friendly":
    st.info("Cost filtering is not active yet because reliable local grocery prices are not available in the source dataset.")

st.header("2. Add items to your cart")
all_ingredients = sorted({ingredient for items in recipes["ingredients"] for ingredient in items})
selected = st.multiselect("Ingredients already selected", options=all_ingredients, placeholder="Search for an ingredient...")
st.write("Selected items: " + str(len(selected)))

st.header("3. Recipe recommendations")
if len(selected) < 3:
    missing = 3 - len(selected)
    st.info("Select " + str(missing) + " more item(s) to see recommendations.")
    st.stop()

# Rank by how many selected cart items the recipe uses. If tied, prefer recipes
# that require fewer additional ingredients, then shorter cooking time.
matches = find_ranked_matches(recipes, selected)

if matches.empty:
    st.warning("No recipes contain any of the selected ingredients in this dataset.")
    st.stop()

top_match_count = int(matches["_match_count"].max())
if top_match_count < len(selected):
    st.info(
        f"No recipe uses all {len(selected)} selected items. The strongest matches use "
        f"{top_match_count} selected items; ties are ranked by how many extra ingredients "
        "the recipe needs."
    )

# Apply the chosen preference to all matching recipes without changing their
# ingredient ranking among the remaining results.
if preference == "Low calorie":
    matches = matches[matches["calories_per_serving"].notna() & (matches["calories_per_serving"] <= 500)]
elif preference == "Quick meal":
    matches = matches[matches["minutes"].notna() & (matches["minutes"] <= 30)]
elif preference == "Balanced meal":
    matches = matches[
        matches["calories_per_serving"].notna()
        & (matches["calories_per_serving"] <= 600)
        & matches["minutes"].notna()
        & (matches["minutes"] <= 45)
    ]

if matches.empty:
    st.warning("Recipes matched your selected ingredients, but none satisfied the chosen preference. Try another preference.")
else:
    st.success(str(len(matches)) + " matching recipe(s)")
    for _, recipe in matches.iterrows():
        with st.container(border=True):
            st.subheader(str(recipe["name"]))
            st.write(
                "Matched cart items: "
                + ", ".join(recipe["_matched_ingredients"])
                + f" ({int(recipe['_match_count'])} of {len(selected)} selected)"
            )
            st.write(f"Additional ingredients needed: {int(recipe['_required_count'])}")
            left, right = st.columns(2)
            with left:
                mins = recipe["minutes"]
                st.write("Time: " + (str(int(mins)) + " minutes" if pd.notna(mins) else "unavailable"))
            with right:
                kcal = recipe["calories_per_serving"]
                st.write("Calories: " + (str(round(kcal)) if pd.notna(kcal) else "unavailable"))
            with st.expander("View cooking instructions"):
                steps = recipe.get("steps", [])
                if steps:
                    for i, step in enumerate(steps, 1):
                        st.write(str(i) + ". " + str(step))
                else:
                    st.write("Instructions unavailable in the source data.")

st.caption(
    "Recipes are ranked by selected cart items matched, then by fewer additional ingredients "
    "needed, and then by cooking time. Your cart selection is not changed."
)
