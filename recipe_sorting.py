"""Deterministic recipe sorting for the customer recommendation view."""
import pandas as pd


SORT_OPTIONS = ("Calories", "Time Taken", "Budget Friendly")


def sort_recipes(matches, criterion):
    """Return (sorted_matches, budget_cost_available).

    All three criteria use fewer additional ingredients as the first tie-breaker.
    Missing primary values are always placed last. Stable sorting preserves the
    incoming order when all available sort keys tie.
    """
    if criterion not in SORT_OPTIONS:
        raise ValueError(f"Unknown recipe sorting criterion: {criterion}")

    results = matches.copy()
    for column in ("calories_per_serving", "minutes", "estimated_cost", "_required_count"):
        if column in results.columns:
            results[column] = pd.to_numeric(results[column], errors="coerce")

    cost_available = (
        "estimated_cost" in results.columns
        and results["estimated_cost"].notna().any()
    )

    if criterion == "Calories":
        columns = ["calories_per_serving", "_required_count", "minutes"]
        ascending = [True, True, True]
        if cost_available:
            columns.append("estimated_cost")
            ascending.append(True)
    elif criterion == "Time Taken":
        columns = ["minutes", "_required_count"]
        ascending = [True, True]
        if cost_available:
            columns.append("estimated_cost")
            ascending.append(True)
        columns.append("calories_per_serving")
        ascending.append(True)
    elif cost_available:
        columns = ["estimated_cost", "_required_count", "minutes", "calories_per_serving"]
        ascending = [True, True, True, True]
    else:
        # Do not invent a recipe cost from ingredient names or per-100g prices.
        columns = ["_required_count", "minutes", "calories_per_serving"]
        ascending = [True, True, True]

    usable_columns = [column for column in columns if column in results.columns]
    usable_ascending = [ascending[i] for i, column in enumerate(columns) if column in results.columns]
    if not usable_columns:
        return results, cost_available

    results = results.sort_values(
        usable_columns,
        ascending=usable_ascending,
        na_position="last",
        kind="stable",
    )
    return results, cost_available
