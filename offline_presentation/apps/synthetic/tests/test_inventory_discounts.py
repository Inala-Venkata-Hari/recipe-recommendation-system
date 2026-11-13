import unittest
import pandas as pd

from inventory_discounts import generate_combo_offers
from recipe_matching import find_ranked_matches


class InventoryDiscountTests(unittest.TestCase):
    def test_surplus_stock_generates_margin_safe_offer(self):
        inventory = pd.DataFrame([
            {"ingredient_name": "tomato", "stock_qty": 100, "required_qty": 20, "unit_cost": 5, "unit_price": 10},
            {"ingredient_name": "onion", "stock_qty": 80, "required_qty": 20, "unit_cost": 4, "unit_price": 9},
        ])
        offers = generate_combo_offers(inventory, max_discount=20, minimum_margin_pct=5)
        self.assertTrue(offers)
        self.assertEqual(set(offers[0]["items"]), {"tomato", "onion"})
        self.assertLessEqual(offers[0]["discount_pct"], 20)

    def test_no_offer_when_stock_does_not_exceed_required_supply(self):
        inventory = pd.DataFrame([
            {"ingredient_name": "rice", "stock_qty": 10, "required_qty": 10, "unit_cost": 5, "unit_price": 10},
            {"ingredient_name": "beans", "stock_qty": 8, "required_qty": 9, "unit_cost": 4, "unit_price": 9},
        ])
        self.assertEqual(generate_combo_offers(inventory), [])

    def test_no_offer_when_margin_floor_cannot_be_preserved(self):
        inventory = pd.DataFrame([
            {"ingredient_name": "a", "stock_qty": 100, "required_qty": 0, "unit_cost": 9.8, "unit_price": 10},
            {"ingredient_name": "b", "stock_qty": 100, "required_qty": 0, "unit_cost": 9.8, "unit_price": 10},
        ])
        self.assertEqual(generate_combo_offers(inventory, minimum_margin_pct=5), [])

    def test_pantry_staples_are_excluded_from_additional_ingredient_count(self):
        recipes = pd.DataFrame([
            {"name": "Simple chicken", "ingredients": ["chicken", "onion", "salt"], "minutes": 20},
            {"name": "Chicken curry", "ingredients": ["chicken", "onion", "salt", "garlic"], "minutes": 30},
        ])
        matches = find_ranked_matches(recipes, ["chicken", "onion"], pantry_items={"salt"})
        simple = matches[matches["name"] == "Simple chicken"].iloc[0]
        curry = matches[matches["name"] == "Chicken curry"].iloc[0]
        self.assertEqual(simple["_required_count"], 0)
        self.assertEqual(curry["_required_count"], 1)

    def test_selected_pantry_staple_is_still_counted_as_cart_match(self):
        recipes = pd.DataFrame([
            {"name": "Simple chicken", "ingredients": ["chicken", "onion", "salt"], "minutes": 20},
        ])
        matches = find_ranked_matches(recipes, ["chicken", "onion", "salt"], pantry_items={"salt"})
        self.assertEqual(matches.iloc[0]["_match_count"], 3)
        self.assertEqual(matches.iloc[0]["_required_count"], 0)


if __name__ == "__main__":
    unittest.main()
