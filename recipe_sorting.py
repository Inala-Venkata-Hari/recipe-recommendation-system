"""Deterministic recipe sorting for the customer recommendation view."""
import pandas as pd


SORT_OPTIONS = ("Calories", "Time Taken", "Budget Friendly")


def sort_recipes(matches, criterion):
    """Return (sorted_matches, budget_cost_available).

    All modes sort by matched cart ingredient count descending first, then
    additional ingredient count ascending.
    The selected preference breaks ties; missing values sort last within a group. Stable sorting preserves the
    incoming order when all available sort keys tie.
    """
    if criterion not in SORT_OPTIONS:
        raise ValueError(f"Unknown recipe sorting criterion: {criterion}")

    results = matches.copy()
    for column in ("calories_per_serving", "minutes", "estimated_cost", "estimated_cost_per_serving", "_required_count", "_match_count"):
        if column in results.columns:
            results[column] = pd.to_numeric(results[column], errors="coerce")

    cost_column = (
        "estimated_cost_per_serving"
        if "estimated_cost_per_serving" in results.columns
        and results["estimated_cost_per_serving"].notna().any()
        else "estimated_cost"
    )
    cost_available = cost_column in results.columns and results[cost_column].notna().any()

    if criterion == "Calories":
        columns = ["_required_count", "calories_per_serving", "minutes"]
        ascending = [True, True, True]
        if cost_available:
            columns.append(cost_column)
            ascending.append(True)
    elif criterion == "Time Taken":
        columns = ["_required_count", "minutes"]
        ascending = [True, True]
        if cost_available:
            columns.append(cost_column)
            ascending.append(True)
        columns.append("calories_per_serving")
        ascending.append(True)
    elif cost_available:
        columns = ["_required_count", cost_column, "minutes", "calories_per_serving"]
        ascending = [True, True, True, True]
    else:
        # Do not invent a recipe cost from ingredient names or per-100g prices.
        columns = ["_required_count", "minutes", "calories_per_serving"]
        ascending = [True, True, True]

    if "_match_count" in results.columns:
        columns.insert(0, "_match_count")
        ascending.insert(0, False)

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
