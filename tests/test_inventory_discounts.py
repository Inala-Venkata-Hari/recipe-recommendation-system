import unittest
import pandas as pd

from inventory_discounts import generate_combo_offers


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


if __name__ == "__main__":
    unittest.main()
