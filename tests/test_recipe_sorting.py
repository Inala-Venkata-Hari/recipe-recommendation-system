import unittest

import pandas as pd

from recipe_sorting import sort_recipes


class RecipeSortingTests(unittest.TestCase):
    def setUp(self):
        self.recipes = pd.DataFrame([
            {"name": "A", "calories_per_serving": 400, "minutes": 30, "_required_count": 1, "estimated_cost": 50},
            {"name": "B", "calories_per_serving": 300, "minutes": 20, "_required_count": 2, "estimated_cost": 40},
            {"name": "C", "calories_per_serving": 400, "minutes": 15, "_required_count": 0, "estimated_cost": 60},
            {"name": "D", "calories_per_serving": 300, "minutes": 20, "_required_count": 1, "estimated_cost": 40},
        ])

    def test_calories_primary_then_required_then_time(self):
        result, cost_available = sort_recipes(self.recipes, "Calories")
        self.assertTrue(cost_available)
        self.assertEqual(result["name"].tolist(), ["D", "B", "C", "A"])

    def test_time_primary_then_required_then_cost_then_calories(self):
        result, cost_available = sort_recipes(self.recipes, "Time Taken")
        self.assertTrue(cost_available)
        self.assertEqual(result["name"].tolist(), ["C", "D", "B", "A"])

    def test_budget_primary_then_required_then_time(self):
        result, cost_available = sort_recipes(self.recipes, "Budget Friendly")
        self.assertTrue(cost_available)
        self.assertEqual(result["name"].tolist(), ["D", "B", "A", "C"])

    def test_budget_does_not_fabricate_missing_costs(self):
        data = self.recipes.drop(columns=["estimated_cost"])
        result, cost_available = sort_recipes(data, "Budget Friendly")
        self.assertFalse(cost_available)
        self.assertEqual(result["name"].tolist(), ["C", "D", "A", "B"])

    def test_budget_sort_places_unknown_costs_last(self):
        data = self.recipes.copy()
        data.loc[data["name"] == "A", "estimated_cost"] = None
        result, cost_available = sort_recipes(data, "Budget Friendly")
        self.assertTrue(cost_available)
        self.assertEqual(result["name"].tolist(), ["D", "B", "C", "A"])

    def test_missing_primary_values_are_sorted_last(self):
        data = self.recipes.copy()
        data.loc[data["name"] == "D", "calories_per_serving"] = None
        result, _ = sort_recipes(data, "Calories")
        self.assertEqual(result.iloc[-1]["name"], "D")

    def test_unknown_sort_option_is_rejected(self):
        with self.assertRaises(ValueError):
            sort_recipes(self.recipes, "Popularity")


if __name__ == "__main__":
    unittest.main()
