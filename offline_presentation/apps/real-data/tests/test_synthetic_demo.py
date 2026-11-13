import ast
import unittest
from pathlib import Path

import pandas as pd

from ingredient_normalization import normalize_ingredient_list
from inventory_discounts import generate_combo_offers
from recipe_matching import find_ranked_matches
from recipe_sorting import sort_recipes
from recipe_costs import add_recipe_cost_estimates


DATA = Path(__file__).resolve().parents[1] / "data" / "synthetic_demo"


class SyntheticDemoIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipes = pd.read_csv(DATA / "recipes_cleaned.csv")
        for column in ("ingredients", "ingredient_quantities", "tags", "steps", "nutrition"):
            cls.recipes[column] = cls.recipes[column].apply(ast.literal_eval)
        cls.recipes["ingredients"] = cls.recipes["ingredients"].apply(normalize_ingredient_list)
        cls.recipes["minutes"] = pd.to_numeric(cls.recipes["minutes"], errors="coerce")
        cls.recipes["calories_per_serving"] = pd.to_numeric(
            cls.recipes["calories_per_serving"], errors="coerce"
        )
        cls.catalog = pd.read_csv(DATA / "ingredient_catalog.csv")
        cls.recipes = add_recipe_cost_estimates(cls.recipes, cls.catalog)
        cls.inventory = pd.read_csv(DATA / "seller_inventory.csv")

    def test_all_synthetic_recipes_have_quantities_and_calculable_costs(self):
        prices = dict(zip(self.catalog["ingredient_name"], self.catalog["price_per_100g"]))
        self.assertTrue(self.recipes["ingredient_quantities"].apply(bool).all())
        costs = []
        for _, recipe in self.recipes.iterrows():
            self.assertEqual(
                {item["name"] for item in recipe["ingredient_quantities"]},
                set(recipe["ingredients"]),
            )
            total = sum(
                item["quantity_g"] * prices[item["name"]] / 100
                for item in recipe["ingredient_quantities"]
            )
            costs.append(round(total, 2))
        self.assertEqual(len(costs), 15)
        self.assertTrue(all(cost > 0 for cost in costs))

    def test_demo_dataset_has_expected_scope_and_unique_ingredients(self):
        self.assertEqual(len(self.recipes), 15)
        all_ingredients = {
            ingredient for ingredients in self.recipes["ingredients"] for ingredient in ingredients
        }
        self.assertEqual(len(all_ingredients), 28)
        self.assertEqual(len(pd.read_csv(DATA / "ingredient_catalog.csv")), 28)

    def test_cart_matching_returns_relevant_ranked_recipes(self):
        matches = find_ranked_matches(
            self.recipes, ["rice", "tomato", "onion"], pantry_items={"cumin", "salt"}
        )
        self.assertFalse(matches.empty)
        self.assertEqual(matches.iloc[0]["name"], "Tomato Rice")
        self.assertEqual(int(matches.iloc[0]["_match_count"]), 3)
        self.assertEqual(int(matches.iloc[0]["_required_count"]), 1)

    def test_all_three_sort_modes_run_on_demo_matches(self):
        matches = find_ranked_matches(self.recipes, ["rice", "tomato", "onion"])
        for criterion in ("Calories", "Time Taken", "Budget Friendly"):
            with self.subTest(criterion=criterion):
                sorted_matches, cost_available = sort_recipes(matches, criterion)
                self.assertFalse(sorted_matches.empty)
                if criterion == "Budget Friendly":
                    self.assertTrue(cost_available)

    def test_seller_inventory_generates_margin_safe_combo_offers(self):
        offers = generate_combo_offers(
            self.inventory, max_discount=15, min_items=2, max_items=4,
            minimum_margin_pct=5, today="2026-11-05"
        )
        self.assertTrue(offers)
        for offer in offers:
            self.assertGreater(offer["discount_pct"], 0)
            self.assertLessEqual(offer["discount_pct"], 15)
            self.assertGreaterEqual(len(offer["items"]), 2)
            rows = self.inventory.set_index("ingredient_name").loc[offer["items"]]
            revenue_after_discount = rows["unit_price"].sum() * (1 - offer["discount_pct"] / 100)
            cost = rows["unit_cost"].sum()
            self.assertGreaterEqual(revenue_after_discount + 0.10, cost / 0.95)


if __name__ == "__main__":
    unittest.main()


class PresentationDataTests(unittest.TestCase):
    def test_inventory_units_prices_and_exclusions(self):
        from inventory_discounts import score_inventory
        inventory = pd.read_csv(DATA / "seller_inventory.csv")
        catalog = pd.read_csv(DATA / "ingredient_catalog.csv").set_index("ingredient_name")
        self.assertTrue(inventory.batch_id.is_unique)
        self.assertTrue((inventory.stock_unit == "100 g pack").all())
        for row in inventory.itertuples():
            self.assertEqual(row.unit_price, catalog.loc[row.ingredient_name, "price_per_100g"])
        scored = score_inventory(inventory, today="2026-11-05").set_index("ingredient_name")
        for name in ["cream", "cucumber", "lentils"]:
            self.assertFalse(scored.loc[name, "eligible"])

    def test_offer_financials_reconcile(self):
        inventory = pd.read_csv(DATA / "seller_inventory.csv")
        for offer in generate_combo_offers(inventory, today="2026-11-05", minimum_margin_pct=15):
            self.assertAlmostEqual(offer["profit"], offer["offer_price"]-offer["cost"], places=2)
            self.assertAlmostEqual(offer["savings"], offer["original_price"]-offer["offer_price"], places=2)
            self.assertGreaterEqual(offer["margin_pct"], 15)
            self.assertIn("100 g pack", offer["quantity_description"])
