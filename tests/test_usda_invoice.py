import unittest
import pandas as pd
from invoice import render_invoice
from usda_workflow import custom_formulation,priced_formulations

class USDAInvoiceAndCustomMealTests(unittest.TestCase):
    def test_invoice_escapes_values_and_reconciles_currency(self):
        lines=[{'Item':'Rice <script>bad</script>','Quantity':'100 g','Regular (USD)':2,'Payable (USD)':1.5,'Savings (USD)':.5,'Batches':'A&B'}]
        html=render_invoice(lines,'2026-11-08','TEST-1',currency='USD')
        self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>bad',html)
        self.assertIn('$2.00',html);self.assertIn('$1.50',html)
        self.assertIn('Currency: USD',html);self.assertNotIn('₹',html)
        self.assertIn('not a tax invoice',html)

    def test_custom_calories_are_weighted_and_not_labeled_usda_measurement(self):
        catalog=pd.DataFrame([dict(food_code=1,name='A',price_per_100g_usd=1,kcal_per_100g=100,protein_per_100g=10),dict(food_code=2,name='B',price_per_100g_usd=2,kcal_per_100g=200,protein_per_100g=20)])
        record=custom_formulation('My meal',{1:200,2:100},catalog,record_id=-1)
        self.assertAlmostEqual(record['kcal_per_100g'],400/3)
        self.assertEqual(record['ingredient_batch_cost_usd'],4)
        self.assertIn('input estimate',record['calorie_basis'])
        self.assertIsNone(record['fdc_id'])
        with self.assertRaises(ValueError):custom_formulation('Invalid',{1:100},catalog)

    def test_inventory_edits_preserve_saved_price_and_changed_stock_invalidates_offer(self):
        from usda_workflow import simulated_batches,validate_inventory_edits,frequency_table,draft_offers
        catalog=pd.DataFrame([dict(food_code=1,name='A',price_per_100g_usd=1),dict(food_code=2,name='B',price_per_100g_usd=2)])
        form=dict(ingredients=[dict(food_code=1),dict(food_code=2)])
        inventory=simulated_batches(form,catalog,'2026-11-08')
        repriced=catalog.copy();repriced['price_per_100g_usd']=100
        edits=inventory.copy();edits.loc[0,'stock_qty']=0
        saved=validate_inventory_edits(edits,inventory,repriced)
        self.assertEqual(saved.iloc[0].unit_price,1)
        offers,scored,_=draft_offers(saved,frequency_table([form]),repriced,'2026-11-08')
        self.assertFalse(offers)
        self.assertEqual(len(scored),2)

    def test_budget_density_breaks_ties_only_after_ingredient_counts(self):
        from build_usda_trial import rank_formulations
        rows=[dict(food_code=1,name='Small expensive batch',ingredients=[{'food_code':10}],ingredient_batch_cost_usd=2,ingredient_batch_grams=100,kcal_per_100g=100),dict(food_code=2,name='Large economical batch',ingredients=[{'food_code':10}],ingredient_batch_cost_usd=10,ingredient_batch_grams=1000,kcal_per_100g=100)]
        self.assertEqual(rank_formulations(rows,[10],'Budget-friendly (per 100 g input)')[0]['food_code'],2)

    def test_catalog_repricing_changes_drafts_and_cash_savings_match_checkout(self):
        from usda_workflow import simulated_batches,frequency_table,draft_offers,customer_lines
        from offer_publishing import publish_snapshot,active_promotions
        catalog=pd.DataFrame([dict(food_code=1,name='A',price_per_100g_usd=1.004),dict(food_code=2,name='B',price_per_100g_usd=2.004)])
        form=dict(ingredients=[dict(food_code=1),dict(food_code=2)])
        inventory=simulated_batches(form,catalog,'2026-11-08')
        classified=frequency_table([form])
        offers,_,_=draft_offers(inventory,classified,catalog,'2026-11-08')
        chosen=offers[0]
        regular=customer_lines({1:100,2:100},[],offers,inventory,catalog)
        self.assertAlmostEqual(chosen['original_price'],sum(r['Payable (USD)'] for r in regular))
        self.assertAlmostEqual(chosen['savings'],chosen['original_price']-chosen['offer_price'])
        self.assertLessEqual(chosen['effective_discount_pct'],30+1e-8)
        snapshots=publish_snapshot(offers,inventory,'2026-11-10','2026-11-08')
        updated=catalog.copy();updated['price_per_100g_usd']=5
        new,_,_=draft_offers(inventory,classified,updated,'2026-11-08')
        self.assertFalse(active_promotions(snapshots,new,'2026-11-08'))
        updated['price_per_100g_usd']=.0001
        self.assertFalse(draft_offers(inventory,classified,updated,'2026-11-08')[0])

    def test_missing_batch_dates_are_rejected_cleanly(self):
        from inventory_batches import create_batch
        catalog=pd.DataFrame({'ingredient_name':['1'],'price_per_100g':[1]})
        with self.assertRaises(ValueError):
            create_batch(catalog,pd.DataFrame(),'1','NEW',10,1,.5,None,'2026-11-10',1,7,7,'2026-11-08')
