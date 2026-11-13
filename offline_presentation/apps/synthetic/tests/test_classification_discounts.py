import unittest
import pandas as pd
from inventory_discounts import classification_parameters, score_inventory, generate_combo_offers

class ClassificationDiscountTests(unittest.TestCase):
    def test_thresholds_and_normalization(self):
        frame = pd.DataFrame({'ingredient_name':[' SALT ', 'rice', 'beans', 'spice'], 'frequency_ratio':[.25,.10,.03,.029]})
        params = classification_parameters(frame)
        self.assertEqual([params[n][2] for n in ['salt','rice','beans','spice']], [1,1.1,1.2,1.3])

    def test_invalid_and_conflicting_classifications_are_neutral(self):
        frame = pd.DataFrame({'ingredient_name':['a','a','b','c'], 'frequency_ratio':[.1,.5,2,float('nan')]})
        self.assertEqual(classification_parameters(frame), {})

    def test_classification_boosts_discount_and_preserves_margin(self):
        inventory = pd.DataFrame([dict(ingredient_name=n, stock_qty=100,required_qty=50,unit_cost=5,unit_price=10) for n in ['salt','spice']])
        frame = pd.DataFrame({'ingredient_name':['salt','spice'], 'frequency_ratio':[.4,.01]})
        scored = score_inventory(inventory, today='2026-11-05', classified=frame)
        self.assertEqual(list(scored.discount_priority), [.5,.65])
        offer = generate_combo_offers(inventory,max_discount=30,classified=frame)[0]
        self.assertAlmostEqual(offer['discount_pct'],17.2)
        baseline = generate_combo_offers(inventory,max_discount=30)[0]
        self.assertGreater(offer['discount_pct'],baseline['discount_pct'])
        offer = generate_combo_offers(inventory,max_discount=100,minimum_margin_pct=40,classified=frame)[0]
        revenue=20*(1-offer['discount_pct']/100)
        self.assertGreaterEqual((revenue-10)/revenue,.4)

    def test_rarity_does_not_discount_stock_without_urgency(self):
        inventory=pd.DataFrame([dict(ingredient_name='spice',stock_qty=10,required_qty=10,unit_cost=5,unit_price=10)])
        frame=pd.DataFrame({'ingredient_name':['spice'],'frequency_ratio':[.01]})
        self.assertFalse(score_inventory(inventory,classified=frame).iloc[0].eligible)
