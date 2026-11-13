import unittest

import pandas as pd

from ingredient_normalization import normalize_ingredient, normalize_ingredient_list
from recipe_matching import find_ranked_matches


class IngredientNormalizationTests(unittest.TestCase):
    def test_case_whitespace_and_hyphen_variants_normalize_together(self):
        variants = ["white rice", "white- rice", "White Rice", " white   rice ", "WHITE-RICE"]
        self.assertEqual({normalize_ingredient(value) for value in variants}, {"white rice"})

    def test_dash_unicode_variants_normalize_to_spaces(self):
        self.assertEqual(normalize_ingredient("brown–rice"), "brown rice")
        self.assertEqual(normalize_ingredient("brown—rice"), "brown rice")

    def test_distinct_ingredient_descriptors_are_preserved(self):
        self.assertNotEqual(normalize_ingredient("rice"), normalize_ingredient("white rice"))
        self.assertNotEqual(normalize_ingredient("chili powder"), normalize_ingredient("chili flakes"))

    def test_normalize_list_removes_duplicates_and_keeps_order(self):
        self.assertEqual(
            normalize_ingredient_list(["White Rice", "white- rice", "salt", "", None, " SALT "]),
            ["white rice", "salt"],
        )


class FindRankedMatchesTests(unittest.TestCase):
    def setUp(self):
        self.recipes = pd.DataFrame(
            [
                {"id": 1, "name": "Exact", "ingredients": ["rice", "beans", "tomato", "onion"], "minutes": 30},
                {"id": 2, "name": "Three matches A", "ingredients": ["rice", "beans", "tomato", "salt"], "minutes": 20},
                {"id": 3, "name": "Three matches B", "ingredients": ["rice", "beans", "onion"], "minutes": 25},
                {"id": 4, "name": "Two matches", "ingredients": ["rice", "beans", "pepper"], "minutes": 15},
                {"id": 5, "name": "No match", "ingredients": ["flour", "sugar"], "minutes": 10},
                {"id": 6, "name": "Same match fewer extras", "ingredients": ["rice", "beans", "tomato"], "minutes": 40},
            ]
        )

    def test_primary_sort_is_match_count(self):
        result = find_ranked_matches(self.recipes, ["rice", "beans", "tomato", "onion"])
        self.assertEqual(result["_match_count"].tolist(), [4, 3, 3, 3, 2])
        self.assertEqual(result["id"].tolist()[:3], [1, 3, 6])

    def test_tie_breaker_prefers_fewer_additional_ingredients(self):
        result = find_ranked_matches(self.recipes, ["rice", "beans", "tomato", "onion"])
        tied = result[result["_match_count"] == 3]
        self.assertEqual(tied["_required_count"].tolist(), [0, 0, 1])
        self.assertEqual(tied["id"].tolist(), [3, 6, 2])

    def test_fewer_additional_items_before_cooking_time(self):
        result = find_ranked_matches(self.recipes, ["rice", "beans", "tomato", "onion", "salt"])
        self.assertEqual(result.iloc[0]["id"], 2)
        self.assertEqual(int(result.iloc[0]["_match_count"]), 4)
        self.assertEqual(int(result.iloc[0]["_required_count"]), 0)

    def test_no_shared_ingredients_returns_empty(self):
        result = find_ranked_matches(self.recipes, ["apple", "orange", "pear"])
        self.assertTrue(result.empty)

    def test_matching_ignores_case_and_outer_spaces(self):
        result = find_ranked_matches(self.recipes, [" RICE ", "BEANS", "Tomato"])
        self.assertEqual(int(result.iloc[0]["_match_count"]), 3)
        self.assertEqual(int(result.iloc[0]["_required_count"]), 0)

    def test_matching_handles_hyphen_variants(self):
        recipes = pd.DataFrame([
            {"id": 1, "name": "Rice", "ingredients": ["white- rice", "beans", "tomato"], "minutes": 15}
        ])
        result = find_ranked_matches(recipes, ["white rice", "beans", "tomato"])
        self.assertEqual(int(result.iloc[0]["_match_count"]), 3)
        self.assertEqual(result.iloc[0]["_matched_ingredients"], ["white rice"])

    def test_empty_selection_returns_empty(self):
        result = find_ranked_matches(self.recipes, [])
        self.assertTrue(result.empty)


if __name__ == "__main__":
    unittest.main()
