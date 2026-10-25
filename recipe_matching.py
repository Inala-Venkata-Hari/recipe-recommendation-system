import pandas as pd


def find_ranked_matches(recipes, selected):
    """Rank recipes by cart overlap, then by how few extra ingredients they need.

    Primary score: more selected cart ingredients matched is better.
    Tie-breaker: fewer recipe ingredients not already in the cart is better.
    Recipes with no selected-ingredient overlap are excluded.
    """
    if not selected or recipes.empty:
        empty = recipes.iloc[0:0].copy()
        empty["_matched_ingredients"] = pd.Series(dtype=object)
        empty["_match_count"] = pd.Series(dtype=int)
        empty["_required_count"] = pd.Series(dtype=int)
        return empty

    selected_by_key = {}
    for ingredient in selected:
        key = str(ingredient).strip().casefold()
        selected_by_key.setdefault(key, str(ingredient).strip())

    selected_keys = list(selected_by_key)

    def normalized_recipe_items(items):
        return {
            str(item).strip().casefold()
            for item in (items if isinstance(items, list) else [])
            if str(item).strip()
        }

    def matched_for_recipe(items):
        recipe_keys = normalized_recipe_items(items)
        return [
            selected_by_key[key]
            for key in selected_keys
            if key in recipe_keys
        ]

    results = recipes.copy()
    results["_matched_ingredients"] = results["ingredients"].apply(matched_for_recipe)
    results["_match_count"] = results["_matched_ingredients"].apply(len)
    results["_required_count"] = results["ingredients"].apply(
        lambda items: max(
            len(normalized_recipe_items(items))
            - len(set(normalized_recipe_items(items)).intersection(selected_by_key)),
            0,
        )
    )

    # A recipe with no matching cart items is not a useful recommendation.
    results = results[results["_match_count"] > 0].copy()

    # Primary: maximize cart matches. Tie-breaker: minimize additional items
    # needed to make the recipe. Final tie-breaker: shorter cooking time.
    sort_columns = ["_match_count", "_required_count"]
    ascending = [False, True]
    if "minutes" in results.columns:
        sort_columns.append("minutes")
        ascending.append(True)

    return results.sort_values(
        sort_columns,
        ascending=ascending,
        na_position="last",
        kind="stable",
    )
