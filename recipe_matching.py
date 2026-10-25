import pandas as pd


def find_best_matches(recipes, selected):
    """Return recipes matching the largest possible subset of selected ingredients.

    A recipe's score is the number of selected cart ingredients it contains.
    Keeping only the maximum score is equivalent to trying n, n-1, n-2, ...
    selected ingredients and stopping at the first subset size that has results.
    """
    if not selected or recipes.empty:
        empty = recipes.iloc[0:0].copy()
        empty["_matched_ingredients"] = pd.Series(dtype=object)
        empty["_match_count"] = pd.Series(dtype=int)
        return empty

    # Compare normalized names so capitalization and surrounding spaces do not
    # prevent an ingredient match. Keep the original selected name for display.
    selected_by_key = {}
    for ingredient in selected:
        key = str(ingredient).strip().casefold()
        selected_by_key.setdefault(key, str(ingredient).strip())

    selected_keys = list(selected_by_key)

    def matched_for_recipe(items):
        recipe_keys = {
            str(item).strip().casefold()
            for item in (items if isinstance(items, list) else [])
        }
        return [
            selected_by_key[key]
            for key in selected_keys
            if key in recipe_keys
        ]

    results = recipes.copy()
    results["_matched_ingredients"] = results["ingredients"].apply(matched_for_recipe)
    results["_match_count"] = results["_matched_ingredients"].apply(len)

    best_count = int(results["_match_count"].max())
    if best_count == 0:
        return results.iloc[0:0].copy()

    # A recipe is represented once, even if it would match multiple subsets.
    # Returning only max-score recipes prioritizes the largest matching subset.
    return results[results["_match_count"] == best_count].copy()
