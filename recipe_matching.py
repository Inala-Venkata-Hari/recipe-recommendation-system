import pandas as pd

from ingredient_normalization import normalize_ingredient, normalize_ingredient_list


_CATEGORY_WEIGHTS = {
    "Common": 0,
    "Moderately common": 1,
    "Specialized": 2,
    "Rare / recipe-specific": 3,
}


def _practicality_for_missing(items, selected_keys, ingredient_categories):
    """Score and describe only the ingredients that are still missing from the cart."""
    missing = [
        item for item in normalize_ingredient_list(items)
        if item not in selected_keys
    ]
    if not missing:
        return 0, "Ready to cook — no additional ingredients"

    categories = [
        ingredient_categories.get(item)
        for item in missing
    ]
    if any(category is None for category in categories):
        label = "Ingredient frequency data incomplete"
    elif "Rare / recipe-specific" in categories:
        label = "Includes rare / recipe-specific ingredients"
    elif "Specialized" in categories:
        label = "Includes specialized ingredients"
    else:
        label = "Mostly common or moderately common ingredients"

    # A lower score means the missing ingredients appear in more recipes in
    # the sampled dataset. Unknown categories receive a neutral-middle score.
    score = sum(_CATEGORY_WEIGHTS.get(category, 2) for category in categories)
    return score, label


def find_ranked_matches(recipes, selected, ingredient_categories=None):
    """Rank recipes by cart overlap, missing items, ingredient practicality, and time.

    Primary score: more selected cart ingredients matched is better.
    Tie-breaker: fewer recipe ingredients not already in the cart is better.
    Next tie-breaker: prefer missing ingredients that occur more often in the
    sampled dataset. This is a dataset-frequency proxy, not a guarantee of local
    availability or price. Final tie-breaker: shorter cooking time.
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
        key = normalize_ingredient(ingredient)
        if key:
            selected_by_key.setdefault(key, key)

    selected_keys = set(selected_by_key)

    def normalized_recipe_items(items):
        return set(normalize_ingredient_list(items))

    def matched_for_recipe(items):
        recipe_keys = normalized_recipe_items(items)
        return [selected_by_key[key] for key in selected_by_key if key in recipe_keys]

    results = recipes.copy()
    results["_matched_ingredients"] = results["ingredients"].apply(matched_for_recipe)
    results["_match_count"] = results["_matched_ingredients"].apply(len)
    results["_required_count"] = results["ingredients"].apply(
        lambda items: len(normalized_recipe_items(items) - selected_keys)
    )

    if ingredient_categories is not None:
        normalized_categories = {
            normalize_ingredient(name): category
            for name, category in ingredient_categories.items()
            if normalize_ingredient(name)
        }
        practicality = results["ingredients"].apply(
            lambda items: _practicality_for_missing(
                items, selected_keys, normalized_categories
            )
        )
        results["_practicality_score"] = practicality.apply(lambda item: item[0])
        results["_practicality_label"] = practicality.apply(lambda item: item[1])

    # A recipe with no matching cart items is not a useful recommendation.
    results = results[results["_match_count"] > 0].copy()

    # Keep cart overlap and the number of missing items ahead of practicality,
    # so a rare ingredient never outweighs a recipe that needs fewer items.
    sort_columns = ["_match_count", "_required_count"]
    ascending = [False, True]
    if ingredient_categories is not None:
        sort_columns.append("_practicality_score")
        ascending.append(True)
    if "minutes" in results.columns:
        sort_columns.append("minutes")
        ascending.append(True)

    return results.sort_values(
        sort_columns,
        ascending=ascending,
        na_position="last",
        kind="stable",
    )
