import unittest
from pathlib import Path
import pandas as pd
from inventory_discounts import generate_combo_offers
from checkout import checkout_lines

class CheckoutTests(unittest.TestCase):
    def setUp(self):
        self.inventory = pd.read_csv(Path(__file__).resolve().parents[1]/'data/synthetic_demo/seller_inventory.csv')
        self.offers = generate_combo_offers(self.inventory, today='2026-11-05')
        self.offer = self.offers[0]
        self.quantities = {n: 150.0 for n in self.offer['items']}
        self.rates = {n: 10.0 for n in self.offer['items']}

    def test_bundle_and_extra_quantities_total_correctly(self):
        lines=checkout_lines(self.quantities,self.rates,[self.offer],self.offers,self.inventory)
        self.assertAlmostEqual(sum(x['Payable (INR)'] for x in lines), self.offer['offer_price']+5*len(self.quantities))
        self.assertAlmostEqual(sum(x['Savings (INR)'] for x in lines),self.offer['savings'])

    def test_duplicate_or_changed_offer_rejected(self):
        with self.assertRaises(ValueError):
            checkout_lines(self.quantities,self.rates,[self.offer,self.offer],self.offers,self.inventory)
        with self.assertRaises(ValueError):
            checkout_lines(self.quantities,self.rates,[self.offer],[],self.inventory)

    def test_insufficient_cart_quantity_or_stock_rejected(self):
        quantities=dict(self.quantities);quantities[self.offer['items'][0]]=50
        with self.assertRaises(ValueError):
            checkout_lines(quantities,self.rates,[self.offer],self.offers,self.inventory)
        inventory=self.inventory.copy();inventory['stock_qty']=.5
        with self.assertRaises(ValueError):
            checkout_lines(self.quantities,self.rates,[self.offer],self.offers,inventory)

    def test_unknown_units_and_missing_prices_rejected(self):
        inventory=self.inventory.copy();inventory['stock_unit']='kg'
        with self.assertRaises(ValueError):
            checkout_lines(self.quantities,self.rates,[self.offer],self.offers,inventory)
        with self.assertRaises(ValueError):
            checkout_lines(self.quantities,{},[],self.offers,self.inventory)

class AutomaticComboTests(unittest.TestCase):
    def test_two_smaller_disjoint_offers_beat_one_large_overlapping_offer(self):
        from checkout import best_missing_combos
        inventory = pd.DataFrame([dict(ingredient_name=n,batch_id=n,stock_qty=5,stock_unit='100 g pack') for n in 'abcd'])
        def offer(items,saving):
            return dict(items=list(items),batch_ids=list(items),savings=saving,offer_price=20-saving,discount_pct=saving)
        offers=[offer('ab',10),offer('ac',6),offer('bd',6)]
        result=best_missing_combos(list('abcd'),offers,inventory)
        self.assertEqual(sum(o['savings'] for o in result),12)
        self.assertEqual(best_missing_combos(['a'],offers,inventory),[])
        result=best_missing_combos(list('abcd'),offers,inventory,chosen=[offers[0]])
        self.assertEqual(result,[])

class MixedCartOfferTests(unittest.TestCase):
    def test_offer_can_cover_one_existing_and_one_missing_item(self):
        from checkout import relevant_recipe_offers
        offers=[dict(items=['rice','beans'],savings=.3),dict(items=['rice','cake'],savings=1),dict(items=['rice'],savings=.2)]
        self.assertEqual(relevant_recipe_offers(['rice','beans'],['beans'],offers),[offers[0]])
        self.assertEqual(relevant_recipe_offers(['rice','beans'],[],offers),[])
