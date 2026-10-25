import unittest

import pandas as pd

from recipe_matching import find_best_matches


class FindBestMatchesTests(unittest.TestCase):
    def setUp(self):
        self.recipes = pd.DataFrame(
            [
                {"id": 1, "name": "Exact", "ingredients": ["rice", "beans", "tomato", "onion"]},
                {"id": 2, "name": "Three matches A", "ingredients": ["rice", "beans", "tomato", "salt"]},
                {"id": 3, "name": "Three matches B", "ingredients": ["rice", "beans", "onion"]},
                {"id": 4, "name": "Two matches", "ingredients": ["rice", "beans", "pepper"]},
                {"id": 5, "name": "No match", "ingredients": ["flour", "sugar"]},
            ]
        )

    def test_exact_match_has_priority(self):
        result = find_best_matches(
            self.recipes,
            ["rice", "beans", "tomato", "onion"],
        )
        self.assertEqual(result["id"].tolist(), [1])
        self.assertEqual(result["_match_count"].tolist(), [4])

    def test_falls_back_to_largest_subset_and_keeps_ties(self):
        result = find_best_matches(
            self.recipes,
            ["rice", "beans", "tomato", "onion", "salt"],
        )
        self.assertEqual(set(result["id"]), {1, 2})
        self.assertTrue((result["_match_count"] == 4).all())
        self.assertNotIn(3, result["id"].tolist())
        self.assertNotIn(4, result["id"].tolist())

    def test_no_shared_ingredients_returns_empty(self):
        result = find_best_matches(self.recipes, ["apple", "orange", "pear"])
        self.assertTrue(result.empty)

    def test_matching_ignores_case_and_outer_spaces(self):
        result = find_best_matches(self.recipes, [" RICE ", "BEANS", "Tomato"])
        self.assertEqual(result["id"].tolist(), [1, 2])
        self.assertTrue((result["_match_count"] == 3).all())

    def test_empty_selection_returns_empty(self):
        result = find_best_matches(self.recipes, [])
        self.assertTrue(result.empty)


if __name__ == "__main__":
    unittest.main()
