"""Explainable schedule-to-recipe rules; never change offer prices or eligibility."""
import pandas as pd
from ingredient_normalization import normalize_ingredient_list

RULES = {
    'Busy / short break': 'Recipes taking 30 minutes or less',
    'Late study/work': 'Recipes taking 20 minutes or less',
    'After workout': 'Recipes containing lentils, chickpeas, paneer, egg or chicken',
    'Family meal': 'Recipes with at least 2 recorded servings',
}


def recipe_fits_schedule(recipe, schedule):
    minutes = pd.to_numeric(recipe.get('minutes'), errors='coerce')
    if schedule == 'Busy / short break':
        return bool(pd.notna(minutes) and 0 < minutes <= 30)
    if schedule == 'Late study/work':
        return bool(pd.notna(minutes) and 0 < minutes <= 20)
    if schedule == 'After workout':
        return bool(set(normalize_ingredient_list(recipe.get('ingredients', []))) & {'lentils','chickpeas','paneer','egg','chicken'})
    if schedule == 'Family meal':
        servings = pd.to_numeric(recipe.get('servings'), errors='coerce')
        return bool(pd.notna(servings) and servings >= 2)
    return False


def schedule_offer_matches(offers, recipes, schedule):
    if schedule not in RULES:
        return {}
    eligible = [row for row in recipes.to_dict('records') if recipe_fits_schedule(row,schedule)]
    result = {}
    from offer_publishing import promotion_id
    for offer in offers:
        items = set(normalize_ingredient_list(offer['items']))
        matches = [str(row['name']) for row in eligible if items.issubset(set(normalize_ingredient_list(row['ingredients'])))]
        if matches:
            result[promotion_id(offer)] = matches
    return result
