import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd
from usda_workflow import (effective_catalog,validate_price_upload,simulated_batches,draft_offers,
    inventory_upload,frequency_table,customer_lines,priced_formulations,schedule_fit)
from invoice import render_invoice

class USDAServicesTests(unittest.TestCase):
    def setUp(self):
        self.catalog=pd.DataFrame([dict(food_code=101,name='Component A',price_per_100g_usd=1.0,kcal_per_100g=100),dict(food_code=102,name='Component B',price_per_100g_usd=2.0,kcal_per_100g=200)])
        self.form=dict(food_code=200,name='Example',ingredients=[dict(food_code=101,name='Component A',grams=200),dict(food_code=102,name='Component B',grams=100)],kcal_per_100g=150,protein_per_100g=12)
        self.inventory=simulated_batches(self.form,self.catalog,'2026-11-08')
        self.classified=frequency_table([self.form])

    def test_prices_keep_reference_intact_and_recalculate_batch(self):
        overrides=pd.DataFrame([dict(food_code=101,selling_price_per_100g_usd=3)])
        updated=effective_catalog(self.catalog,overrides)
        self.assertEqual(self.catalog.iloc[0].price_per_100g_usd,1)
        self.assertEqual(updated.iloc[0].price_per_100g_usd,3)
        record=priced_formulations([self.form],updated)[0]
        self.assertEqual(record['ingredient_batch_cost_usd'],8)
        self.assertEqual(updated.iloc[0].kcal_per_100g,100)
        for bad in [pd.DataFrame([dict(food_code=999,selling_price_per_100g_usd=1)]),pd.DataFrame([dict(food_code=101,selling_price_per_100g_usd=-1)]),pd.DataFrame([dict(food_code=101,selling_price_per_100g_usd=float('inf'))]),pd.DataFrame([dict(food_code=101.5,selling_price_per_100g_usd=1)])]:
            with self.assertRaises(ValueError):validate_price_upload(bad,self.catalog)

    def test_simulated_inventory_and_cent_safe_margin(self):
        self.assertTrue(self.inventory.inventory_origin.str.startswith('SIMULATED').all())
        offers,_,_=draft_offers(self.inventory,self.classified,self.catalog,'2026-11-08',minimum_margin=25)
        self.assertTrue(offers)
        self.assertEqual(offers[0]['currency'],'USD')
        self.assertGreaterEqual(offers[0]['margin_pct'],25)
        self.assertGreater(offers[0]['savings'],0)
        self.assertIn('Component A',offers[0]['quantity_description'])
        self.assertFalse(draft_offers(self.inventory,self.classified,self.catalog,'2026-11-11')[0])
        self.assertFalse(draft_offers(self.inventory,self.classified,self.catalog,'2026-11-08',max_discount=0)[0])

    def test_candidate_limit_bounds_combinations(self):
        catalog=pd.DataFrame([dict(food_code=n,name=f'Food {n}',price_per_100g_usd=1) for n in range(100,120)])
        form=dict(ingredients=[dict(food_code=n) for n in range(100,120)])
        inventory=simulated_batches(form,catalog,'2026-11-08')
        offers,_,omitted=draft_offers(inventory,frequency_table([form]),catalog,'2026-11-08',candidate_limit=6,max_items=4)
        self.assertEqual(omitted,14)
        self.assertLessEqual(len(offers),50) # C(6,2)+C(6,3)+C(6,4)

    def test_inventory_upload_uses_catalog_price_and_keeps_excluded_batches_visible(self):
        upload=pd.DataFrame([dict(food_code=101,batch_id='EXPIRED',stock_qty=0,required_qty=0,unit_cost=.6,unit_price=999,received_date='2026-11-01',expiry_date='2026-11-07')])
        inventory=inventory_upload(upload,self.catalog)
        self.assertEqual(inventory.iloc[0].unit_price,1)
        offers,scored,_=draft_offers(inventory,self.classified,self.catalog,'2026-11-08')
        self.assertFalse(offers);self.assertFalse(scored.iloc[0].eligible)
        with self.assertRaises(ValueError):inventory_upload(pd.concat([upload,upload]),self.catalog)

    def test_checkout_and_invoice_are_usd_and_pause_blocks_checkout(self):
        offers,_,_=draft_offers(self.inventory,self.classified,self.catalog,'2026-11-08')
        quantities={101:200,102:100}
        lines=customer_lines(quantities,[offers[0]],offers,self.inventory,self.catalog)
        self.assertTrue(all('Payable (USD)' in row and 'Payable (INR)' not in row for row in lines))
        html=render_invoice(lines,'2026-11-08',currency='USD')
        self.assertIn('Currency: USD',html);self.assertNotIn('₹',html)
        self.assertIn('Print / Save as PDF',html)
        with self.assertRaises(ValueError):customer_lines(quantities,[offers[0]],[],self.inventory,self.catalog)

    def test_context_requires_metadata_and_uses_explicit_protein_basis(self):
        self.assertFalse(schedule_fit(self.form,'Busy / short break'))
        self.assertTrue(schedule_fit(self.form,'Busy / short break',{'minutes':30}))
        self.assertFalse(schedule_fit(self.form,'Late study/work',{'minutes':25}))
        self.assertTrue(schedule_fit(self.form,'Family meal',{'servings':2}))
        self.assertTrue(schedule_fit(self.form,'After workout'))

ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless((ROOT/'data/usda_trial/manifest.json').exists(),'Build local USDA profile first')
class USDAWorkflowIntegrationTests(unittest.TestCase):
    def test_publish_auto_apply_invoice_pause_and_reset(self):
        from streamlit.testing.v1 import AppTest
        source=ROOT/'data/usda_trial'
        forms=json.loads((source/'formulations.json').read_text())
        example=next(f for f in forms if f['name']=='Black beans with meat')
        self.assertEqual(len(example['ingredients']),3)
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'USDA_WORK_DIR':folder}):
            app=AppTest.from_file(str(ROOT/'usda_trial.py')).run(timeout=30)
            self.assertFalse(app.exception)
            next(w for w in app.selectbox if w.label=='Inventory example formulation').set_value(example['food_code']).run(timeout=30)
            next(b for b in app.button if b.label=='Load simulated example batches').click().run(timeout=30)
            self.assertFalse(app.exception)
            next(w for w in app.checkbox if w.label=='Select all draft offers for publishing').check().run(timeout=30)
            next(b for b in app.button if b.label=='Publish selected offers').click().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual(next(m for m in app.metric if m.label=='Active published offers').value,'3')
            app.multiselect(key='usda_selected').set_value([example['ingredients'][0]['food_code']]).run(timeout=30)
            app.button(key=f"usda_missing_{example['food_code']}").click().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual(len(app.session_state['usda_chosen_combos']),1)
            self.assertNotEqual(next(m for m in app.metric if m.label=='Applied combo savings (USD)').value,'$0.00')
            next(b for b in app.button if b.label=='Confirm simulated checkout').click().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertIn(b'Currency: USD',app.session_state['usda_receipt'])
            self.assertNotIn('₹'.encode(),app.session_state['usda_receipt'])
            promo=app.session_state['usda_chosen_combos'][0]['promotion_id']
            app.multiselect(key='usda_pause_ids').set_value([promo]).run(timeout=30)
            next(b for b in app.button if b.label=='Pause selected offers').click().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertTrue(any('offer changed or expired' in e.value for e in app.error))
            self.assertFalse(any(b.label=='Confirm simulated checkout' for b in app.button))
            next(b for b in app.button if b.label=='Reset USDA trial').click().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertFalse(app.multiselect(key='usda_selected').value)
            self.assertTrue((Path(folder)/'seller_inventory.csv').exists())

    def test_combo_with_one_selected_and_one_missing_component(self):
        from streamlit.testing.v1 import AppTest
        forms=json.loads((ROOT/'data/usda_trial/formulations.json').read_text())
        example=next(f for f in forms if f['name']=='Beans and brown rice')
        codes=[i['food_code'] for i in example['ingredients']]
        self.assertEqual(len(codes),2)
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'USDA_WORK_DIR':folder}):
            app=AppTest.from_file(str(ROOT/'usda_trial.py')).run(timeout=30)
            next(w for w in app.selectbox if w.label=='Inventory example formulation').set_value(example['food_code']).run(timeout=30)
            next(b for b in app.button if b.label=='Load simulated example batches').click().run(timeout=30)
            next(w for w in app.checkbox if w.label=='Select all draft offers for publishing').check().run(timeout=30)
            next(b for b in app.button if b.label=='Publish selected offers').click().run(timeout=30)
            app.multiselect(key='usda_selected').set_value([codes[0]]).run(timeout=30)
            prefix=f"usda_recipe_combo_{example['food_code']}_"
            buttons=[b for b in app.button if b.key and b.key.startswith(prefix)]
            self.assertEqual(len(buttons),1)
            self.assertFalse(buttons[0].disabled)
            app.button(key=f"usda_missing_{example['food_code']}").click().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual(set(app.multiselect(key='usda_selected').value),set(codes))
            chosen=app.session_state['usda_chosen_combos']
            self.assertEqual(len(chosen),1)
            self.assertEqual(set(chosen[0]['items']),set(map(str,codes)))
            savings=next(m for m in app.metric if m.label=='Applied combo savings (USD)').value
            self.assertEqual(savings,f"${chosen[0]['savings']:.2f}")
            for code in codes:
                self.assertGreaterEqual(app.session_state[f'usda_grams_{code}'],100)

    def test_custom_meal_context_and_seller_price_persistence(self):
        from streamlit.testing.v1 import AppTest
        forms=json.loads((ROOT/'data/usda_trial/formulations.json').read_text())
        example=next(f for f in forms if f['name']=='Beans and brown rice')
        codes=[i['food_code'] for i in example['ingredients']]
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'USDA_WORK_DIR':folder}):
            app=AppTest.from_file(str(ROOT/'usda_trial.py')).run(timeout=30)
            app.multiselect(key='usda_custom_codes').set_value(codes).run(timeout=30)
            next(w for w in app.text_input if w.label=='Meal name').set_value('AAA trial meal')
            next(w for w in app.number_input if w.label=='Optional preparation time (minutes)').set_value(15.0)
            next(w for w in app.number_input if w.label=='Optional declared servings').set_value(2)
            next(b for b in app.button if b.label=='Save component meal').click().run(timeout=30)
            self.assertFalse(app.exception)
            saved=json.loads((Path(folder)/'custom_formulations.json').read_text())
            self.assertEqual(saved[0]['origin'],'User-entered component meal')
            next(w for w in app.selectbox if w.label=='Example formulation').set_value(saved[0]['food_code']).run(timeout=30)
            next(b for b in app.button if b.label=='Load example ingredients').click().run(timeout=30)
            next(w for w in app.selectbox if w.label=='Optional schedule context').set_value('Busy / short break').run(timeout=30)
            self.assertFalse(app.exception)
            self.assertTrue(any('Fits your schedule:' in c.value for c in app.caption))
            app.selectbox(key='usda_reprice_food').set_value(codes[0]).run(timeout=30)
            next(w for w in app.number_input if w.label=='Seller selling price per 100 g (USD)').set_value(3.0)
            next(b for b in app.button if b.label=='Save seller price').click().run(timeout=30)
            self.assertFalse(app.exception)
            prices=pd.read_csv(Path(folder)/'seller_prices.csv')
            self.assertEqual(prices.iloc[0].selling_price_per_100g_usd,3)
            self.assertTrue(any(m.label=='Selected ingredient total (USD)' for m in app.metric))


class ServingScalingTests(unittest.TestCase):
    def test_declared_servings_and_estimated_portion(self):
        from usda_workflow import one_serving_formulation
        source={'ingredients':[{'grams':200,'batch_cost_usd':2},{'grams':100,'batch_cost_usd':3}]}
        declared=one_serving_formulation(source,servings=2)
        self.assertEqual([i['grams'] for i in declared['ingredients']],[100,50])
        self.assertEqual(declared['ingredient_batch_cost_usd'],2.5)
        estimated=one_serving_formulation(source,portion_grams=150)
        self.assertEqual(estimated['ingredient_batch_grams'],150)
        self.assertEqual(estimated['ingredient_batch_cost_usd'],2.5)
        self.assertEqual(source['ingredients'][0]['grams'],200)
        with self.assertRaises(ValueError):one_serving_formulation(source,servings=0)
